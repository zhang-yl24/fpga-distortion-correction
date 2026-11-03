"""One LOAD_ARM command and ACK protocol. File/CPU only: never opens hardware."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import os
import secrets
import struct
import sys
import tempfile
import time
import zlib

from session_v3.snapshot_b1.host.decoder import IdentityError, SequenceTracker, StreamDecoder, compare_golden

ARMED=0x01
BAD_ARGUMENT=0x10
STALE_TICKET=0x11
NONCE_REUSE=0x12
DUPLICATE=0x13
ABORTED=0x14
STATUSES={ARMED,BAD_ARGUMENT,STALE_TICKET,NONCE_REUSE,DUPLICATE,ABORTED}

class ControlError(ValueError):
    pass

@dataclass(frozen=True)
class Request:
    ticket: int
    nonce: int

@dataclass(frozen=True)
class Ack:
    ticket: int
    nonce: int
    status: int
    epoch: int=0

@dataclass(frozen=True)
class LedgerCheckpoint:
    """Caller must establish this is independently current, not another old copy."""
    lineage: str
    next_ticket: int
    sha256: str

def valid_u32(value, *, nonzero=False):
    return type(value) is int and (1 if nonzero else 0) <= value <= 0xffffffff

def envelope(magic, code, ticket, nonce, word):
    require_nonzero=magic==b'SGA1' or code==ARMED
    if not valid_u32(ticket,nonzero=require_nonzero) or not valid_u32(nonce,nonzero=require_nonzero) or not valid_u32(word):
        raise ControlError('ticket/nonce/word outside supported range')
    body=struct.pack('<4sBBHIII',magic,1,code,24,ticket,nonce,word)
    return body+struct.pack('<I',zlib.crc32(body))

def encode_request(request):
    return envelope(b'SGA1',1,request.ticket,request.nonce,0)

def encode_ack(ack):
    if ack.status not in STATUSES or (ack.status!=ARMED and ack.epoch!=0):
        raise ControlError('unsupported ACK status/epoch')
    return envelope(b'SGK1',ack.status,ack.ticket,ack.nonce,ack.epoch)

def decode_control(packet, *, ack=False):
    if len(packet)!=24 or packet[:4]!=(b'SGK1' if ack else b'SGA1'):
        raise ControlError('control framing')
    if zlib.crc32(packet[:20])!=struct.unpack_from('<I',packet,20)[0]:
        raise ControlError('control CRC; pixel CRC is separate')
    _,version,code,length,ticket,nonce,word=struct.unpack('<4sBBHIII',packet[:20])
    if version!=1 or length!=24:
        raise ControlError('control schema')
    if ack:
        if code not in STATUSES or (code!=ARMED and word!=0) or (code==ARMED and (ticket==0 or nonce==0)):
            raise ControlError('ACK status/epoch')
        return Ack(ticket,nonce,code,word)
    if code!=1 or word!=0 or ticket==0 or nonce==0:
        raise ControlError('unsupported command or reserved field')
    return Request(ticket,nonce)

class ControlStream:
    """Exactly one fixed control frame kind, bounded to 24 bytes."""
    def __init__(self, *, ack=False):
        self.ack=ack
        self.magic=b'SGK1' if ack else b'SGA1'
        self.buffer=bytearray()
        self.bad=self.discarded=self.max_buffer=0

    def flush_partial(self):
        if self.buffer:
            self.bad+=1
            self.discarded+=len(self.buffer)
            self.buffer.clear()

    def feed(self,data):
        result=[]
        for value in data:
            self.buffer.append(value)
            self.max_buffer=max(self.max_buffer,len(self.buffer))
            while self.buffer and not self.magic.startswith(self.buffer[:min(4,len(self.buffer))]):
                del self.buffer[0]
                self.discarded+=1
            if len(self.buffer)==24:
                try:
                    frame=decode_control(bytes(self.buffer),ack=self.ack)
                except ControlError:
                    self.bad+=1
                    del self.buffer[0]
                    self.discarded+=1
                    while self.buffer and not self.magic.startswith(self.buffer[:min(4,len(self.buffer))]):
                        del self.buffer[0]
                        self.discarded+=1
                else:
                    result.append(frame)
                    self.buffer.clear()
        return result

class NonceLedger:
    """Explicitly initialized, single-writer, never-reuse ledger per device lineage.

    Atomic replace + fsync assumes a durable local filesystem. Loss/deletion,
    power-loss directory persistence and copying a ledger across independent
    writers are not silently repaired or treated as a new trusted lineage.
    """
    def __init__(self,path,lineage):
        self.path=Path(path)
        if not lineage or not isinstance(lineage,str):
            raise ControlError('explicit device/test lineage required')
        self.lineage=lineage
        self._checkpoint=None

    @property
    def checkpoint(self):
        if self._checkpoint is None:
            raise ControlError('ledger continuity unproven; an independently current checkpoint is required')
        return self._checkpoint

    def resume_from_trusted_checkpoint(self,checkpoint):
        # This is an explicit trust boundary, not discovery or self-certification.
        # A stale ledger AND stale trusted checkpoint cannot be distinguished here.
        if not isinstance(checkpoint,LedgerCheckpoint) or checkpoint.lineage!=self.lineage or \
            type(checkpoint.next_ticket) is not int or not 1<=checkpoint.next_ticket<=0x100000000 or \
            not isinstance(checkpoint.sha256,str) or len(checkpoint.sha256)!=64 or \
            any(c not in '0123456789abcdef' for c in checkpoint.sha256):
            raise ControlError('invalid trusted checkpoint')
        self._checkpoint=checkpoint

    def initialize_new_lineage(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={'version':1,'lineage':self.lineage,'next_ticket':1,'used_nonces':[]}
        descriptor=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
            json.dump(data,handle,sort_keys=True)
            handle.write('\n');handle.flush();os.fsync(handle.fileno())
        self._checkpoint=LedgerCheckpoint(self.lineage,1,hashlib.sha256(self.path.read_bytes()).hexdigest())

    def reserve(self,randbits=None):
        randbits=secrets.randbits if randbits is None else randbits
        lock=self.path.with_name(self.path.name+'.lock')
        descriptor=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(descriptor)
        temporary=None
        try:
            raw=self.path.read_bytes()
            data=json.loads(raw)  # missing/corrupt fails closed
            if not isinstance(data,dict):
                raise ControlError('ledger must be an object')
            used=data.get('used_nonces')
            ticket=data.get('next_ticket')
            if data.get('version')!=1 or data.get('lineage')!=self.lineage or not isinstance(used,list) or \
                any(not valid_u32(n,nonzero=True) for n in used) or len(used)!=len(set(used)) or \
                type(ticket) is not int or not 1<=ticket<=0x100000000:
                raise ControlError('ledger schema/lineage invalid; do not recreate silently')
            if ticket!=len(used)+1:
                raise ControlError('ledger ticket/history count inconsistent; no reservation')
            checkpoint=self.checkpoint  # no automatic trust on process restart
            if checkpoint.next_ticket!=ticket or checkpoint.sha256!=hashlib.sha256(raw).hexdigest():
                raise ControlError('ledger continuity/checkpoint mismatch; possible rollback or replacement')
            if ticket>0xffffffff:
                raise ControlError('ticket exhausted; no wrap')
            issued=set(used)
            nonce=None
            for _ in range(128):
                candidate=randbits(32)
                if valid_u32(candidate,nonzero=True) and candidate not in issued:
                    nonce=candidate
                    break
            if nonce is None:
                raise ControlError('entropy repeated used/zero nonces; fail closed')
            data['used_nonces'].append(nonce)
            data['next_ticket']=ticket+1
            fd,name=tempfile.mkstemp(prefix=self.path.name+'.pending-',dir=self.path.parent)
            temporary=Path(name)
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                json.dump(data,handle,sort_keys=True)
                handle.write('\n');handle.flush();os.fsync(handle.fileno())
            intended_hash=hashlib.sha256(temporary.read_bytes()).hexdigest()
            os.replace(temporary,self.path)
            temporary=None
            self._checkpoint=LedgerCheckpoint(self.lineage,ticket+1,intended_hash)
            return Request(ticket,nonce)  # only after durable reservation
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            lock.unlink()

class AcquisitionGuard:
    """A new challenge -> matching ARMED ACK -> complete matching golden record."""
    def __init__(self,ledger,expected,*,param_id,mode,timeout_seconds=2.0):
        self.ledger=ledger
        self.expected=expected
        self.param_id,self.mode=param_id,mode
        self.timeout_seconds=timeout_seconds
        self.ignored_acks=self.ignored_records=self.pre_ack_records=0
        self.barrier('initial')

    def barrier(self,reason):
        self.state='NEEDS_CHALLENGE'
        self.reason=reason
        self.pending=None
        self.ack_epoch=None
        self.tracker=None
        self.deadline=None
        self.ack_stream=ControlStream(ack=True)
        self.record_stream=StreamDecoder()

    def begin(self,*,now=None,randbits=None):
        self.barrier('new acquisition challenge')
        request=self.ledger.reserve(randbits)
        self.pending=request
        self.state='WAIT_ACK'
        self.deadline=(time.monotonic() if now is None else now)+self.timeout_seconds
        return encode_request(request)

    def check_deadline(self,now=None):
        now=time.monotonic() if now is None else now
        if self.state in ('WAIT_ACK','WAIT_FRAME') and now>=self.deadline:
            self.barrier('timeout; new challenge required')
            return False
        return True

    def accept_ack(self,ack,*,now=None):
        if not self.check_deadline(now):
            self.ignored_acks+=1
            return False
        if self.pending is None or (ack.ticket,ack.nonce)!=(self.pending.ticket,self.pending.nonce):
            self.ignored_acks+=1
            return False
        if self.state!='WAIT_ACK':
            self.ignored_acks+=1
            return False
        if ack.status!=ARMED:
            self.state='FAILED'
            self.reason='current arm request rejected: '+hex(ack.status)
            return False
        self.ack_epoch=ack.epoch
        self.tracker=SequenceTracker(self.pending.nonce)
        self.state='WAIT_FRAME'
        return True

    def accept_record(self,record,*,now=None):
        if not self.check_deadline(now):
            self.ignored_records+=1
            return False
        if self.pending is None or record.session_id!=self.pending.nonce:
            self.ignored_records+=1
            return False
        if self.state=='WAIT_ACK':
            self.pre_ack_records+=1
            return False
        if self.state not in ('WAIT_FRAME','VERIFIED'):
            self.ignored_records+=1
            return False
        if ((record.scan_epoch-self.ack_epoch)&0xffffffff)>=0x80000000:
            self.ignored_records+=1
            return False
        try:
            compare_golden(record,self.expected,session_id=self.pending.nonce,
                           param_id=self.param_id,mode=self.mode)
            self.tracker.accept(record)
        except ValueError:
            self.state='FAILED'
            self.reason='record identity/golden/order failure'
            raise
        self.state='VERIFIED'
        return True

    def feed_acks(self,data,*,now=None):
        return [self.accept_ack(ack,now=now) for ack in self.ack_stream.feed(data)]

    def feed_records(self,data,*,now=None):
        return [self.accept_record(record,now=now) for record in self.record_stream.feed(data)]

def main():
    parser=argparse.ArgumentParser(description='Write a fresh LOAD_ARM command file; no serial access')
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--lineage',required=True)
    parser.add_argument('--command-file',type=Path,required=True)
    parser.add_argument('--init-new-lineage',action='store_true')
    parser.add_argument('--trusted-checkpoint',type=Path,
                        help='independently current external checkpoint; an old backup is not proof')
    args=parser.parse_args()
    ledger=NonceLedger(args.ledger,args.lineage)
    if args.init_new_lineage:
        if args.trusted_checkpoint:
            parser.error('choose a genuinely new lineage or a trusted resume checkpoint')
        ledger.initialize_new_lineage()
    elif args.trusted_checkpoint:
        ledger.resume_from_trusted_checkpoint(LedgerCheckpoint(**json.loads(args.trusted_checkpoint.read_text(encoding='utf-8'))))
    request=ledger.reserve()
    args.command_file.write_bytes(encode_request(request))
    print(json.dumps({'ticket':request.ticket,'nonce':request.nonce,'bytes':24,
                      'checkpoint':ledger.checkpoint.__dict__,
                      'state':'command file only; no hardware load or ACK observed'}))

if __name__=='__main__':
    try:
        main()
    except (ControlError,OSError,ValueError,TypeError) as error:
        print(json.dumps({'state':'BLOCKED','reason':str(error),'hardware_access':False}),file=sys.stderr)
        raise SystemExit(2)

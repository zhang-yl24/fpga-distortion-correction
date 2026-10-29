"""Owned PID tree cleanup, extracted from the already-used offline runner."""
from pathlib import Path
import os,re,subprocess,time
def tool(bin_dir,name,args,work,deadline,stage,env):
    # Fixed .bat invocation and owned PID tree cleanup adapted from the bound
    # project run_gamma_pipeline_d5_sim.tool. No global process enumeration.
    tokens = [str(bin_dir/name),*map(str,args)]
    if not Path(tokens[0]).is_file() or any(re.search(r'["\r\n&|<>^%!]',t) for t in tokens):
        raise ValueError("Invalid fixed simulation tool/argument")
    comspec = os.environ.get("ComSpec","cmd.exe")
    if re.search(r'["\r\n&|<>^%!]',comspec):
        raise ValueError("Invalid command interpreter")
    line = '"'+comspec+'" /d /s /c "'+" ".join('"'+t+'"' for t in tokens)+'"'
    process = None
    with (work/(stage+"-stdout.log")).open("xb") as out,(work/(stage+"-stderr.log")).open("xb") as err:
        try:
            remaining = deadline-time.monotonic()
            if remaining<=0:
                raise TimeoutError("Shared 90s tool budget exhausted")
            process = subprocess.Popen(line,cwd=work,stdout=out,stderr=err,env=env,
                                       creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            code = process.wait(timeout=remaining)
            if code:
                raise RuntimeError(name+" exit="+str(code))
        finally:
            if process is not None and process.poll() is None:
                stopped = subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/taskkill.exe"),
                                          "/PID",str(process.pid),"/T","/F"],capture_output=True,timeout=15)
                (work/(stage+"-owned-stop.log")).write_bytes(stopped.stdout+stopped.stderr)
                process.wait(timeout=15)

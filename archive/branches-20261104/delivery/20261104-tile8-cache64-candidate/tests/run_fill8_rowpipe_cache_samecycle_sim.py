import os,re,subprocess,time
def run_tool(binary, name, args, work, deadline, stem):
    tokens = [str(binary/name), *args]
    if any(re.search(r'["\r\n&|<>^%!]', token) for token in tokens):
        raise ValueError('unsafe simulation argument')
    command = '"'+os.environ.get('ComSpec', 'cmd.exe')+'" /d /s /c "'+' '.join('"'+token+'"' for token in tokens)+'"'
    with (work/(stem+'-stdout.log')).open('xb') as out, (work/(stem+'-stderr.log')).open('xb') as err:
        completed = subprocess.run(command, cwd=work, stdout=out, stderr=err,
            timeout=max(.01, deadline-time.monotonic()), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.returncode:
        raise ValueError(stem+' failed; inspect '+str(work/(stem+'-stdout.log')))


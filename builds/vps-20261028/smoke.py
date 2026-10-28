import subprocess,tempfile,pathlib,secrets,time,urllib.request,json
image='synthpulse-webui:pi-clean-desktop-20261028';name='iuvenis-clean-smoke-20261028'
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t)/'env';p.write_text('SP_WEBUI_PASSWORD='+secrets.token_urlsafe(32)+'\nSP_WEBUI_PASSWORD_IDENTITY=ed@iuvenis.com\n');p.chmod(0o600)
 subprocess.run(['docker','run','-d','--name',name,'--env-file',str(p),'-p','127.0.0.1::8787',image],check=True,capture_output=True)
 try:
  port=subprocess.check_output(['docker','port',name,'8787/tcp'],text=True).strip()
  for i in range(60):
   try:
    with urllib.request.urlopen('http://'+port+'/health',timeout=3) as r:
     if r.status==200:break
   except Exception:time.sleep(2)
  else:raise RuntimeError('Clean WebUI health failed')
  subprocess.run(['docker','exec',name,'python','-c','from run_agent import AIAgent;import mcp,aiohttp,mnemosyne,docx,openpyxl,pptx,pypdf; print("imports passed")'],check=True)
  print(json.dumps({'clean_webui_health':200,'engine_import':True,'document_libraries':True,'provider_authenticated':False,'pi_boot_tested':False}))
 finally:subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)

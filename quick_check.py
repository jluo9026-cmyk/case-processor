import urllib.request
r = urllib.request.urlopen('https://case-processor.onrender.com/tools/report_generate/report_generate.js', timeout=10)
c = r.read().decode('utf-8')
if 'openOcrDetails' in c:
    print('NEW: 新版已部署!')
    print('openOcrDetails found in JS')
else:
    print('OLD: 旧版仍在运行')
    print('JS length:', len(c))
    print('First 200 chars:', c[:200])
</write_to_file>
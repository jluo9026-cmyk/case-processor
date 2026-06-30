import urllib.request, json, sys

# Check GitHub raw
try:
    r = urllib.request.urlopen('https://raw.githubusercontent.com/jluo9026-cmyk/case-processor/main/tools/attachment_tool.html', timeout=10)
    print('GitHub: EXISTS, size=%d bytes' % len(r.read()))
except Exception as e:
    print('GitHub: ERROR - %s' % str(e)[:80])

# Check Render service
try:
    r = urllib.request.urlopen('https://case-processor.onrender.com/tools/attachment_tool.html', timeout=10)
    print('Render: EXISTS, size=%d bytes' % len(r.read()))
except Exception as e:
    print('Render: ERROR - %s' % str(e)[:80])

# Check Render deploy status (no auth, just check header)
try:
    r = urllib.request.urlopen('https://case-processor.onrender.com/api/health', timeout=5)
    print('API: OK')
except Exception as e:
    print('API: %s' % str(e)[:80])
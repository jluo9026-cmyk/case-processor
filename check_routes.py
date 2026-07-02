import sys, os
sys.path.insert(0, 'e:/案件处理启动器')
# Reset environment to avoid OOM
os.environ['DEEPSEEK_API_KEY'] = ''
os.environ['BAIDU_API_KEY'] = ''
os.environ['BAIDU_SECRET_KEY'] = ''
os.environ['QWEN_VL_API_KEY'] = ''

try:
    from modules.app_core import app
    routes = [r.path for r in app.routes]
    print(f'SUCCESS: {len(routes)} routes registered')
    for r in sorted(routes):
        print(f'  {r}')
except Exception as e:
    import traceback
    print(f'ERROR: {e}')
    traceback.print_exc()
import urllib.request
import json
import urllib.error
import sys

# 1. 登录获取 Token
login_data = json.dumps({
    'username': 'student@example.com',
    'password': 'password123'
}).encode('utf-8')

req = urllib.request.Request('http://localhost:8000/api/v1/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        token = json.loads(response.read())['access_token']
        print('✅ 登录成功')
except urllib.error.HTTPError as e:
    print(f'❌ 登录失败: {e.code}')
    print(e.read().decode('utf-8'))
    sys.exit(1)

# 2. 测试获取分类
req = urllib.request.Request('http://localhost:8000/api/v1/knowledge/categories', headers={'Authorization': f'Bearer {token}'})
try:
    with urllib.request.urlopen(req) as response:
        categories = json.loads(response.read())
        print('\n✅ 分类API返回:')
        print(json.dumps(categories, indent=2, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print(f'\n❌ 分类API报错: {e.code}')
    print(e.read().decode('utf-8'))

# 3. 测试搜索
search_url = urllib.parse.quote('http://localhost:8000/api/v1/knowledge/search?query=选课流程', safe=':/?=')
req = urllib.request.Request(search_url, headers={'Authorization': f'Bearer {token}'})
try:
    with urllib.request.urlopen(req) as response:
        search_res = json.loads(response.read())
        print('\n✅ 搜索API返回成功')
        print(json.dumps(search_res, indent=2, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print(f'\n❌ 搜索API报错: {e.code}')
    print(e.read().decode('utf-8'))

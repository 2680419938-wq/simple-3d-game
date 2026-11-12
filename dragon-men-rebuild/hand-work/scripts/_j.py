
import json
d = json.load(open(r'D:\ai\建模\dragon-men-rebuild\hand-work\verify\hand_geom.json', encoding='utf-8'))
def walk(o, path='', depth=0):
    if depth > 3: return
    if isinstance(o, dict):
        ks = list(o.keys())
        print('  '*depth + path + ' dict(%d): %s' % (len(ks), ks[:16]))
        for k in ks[:8]:
            walk(o[k], k, depth+1)
    elif isinstance(o, list):
        print('  '*depth + path + ' list len=%d' % len(o))
        if o: walk(o[0], path+'[0]', depth+1)
    else:
        print('  '*depth + path + ' = ' + repr(o)[:110])
walk(d)

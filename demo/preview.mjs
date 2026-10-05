import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
const root = resolve('dist');
const types = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.mp4':'video/mp4','.jpg':'image/jpeg'};
http.createServer(async(req,res)=>{
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const path = resolve(root, '.' + (pathname==='/'?'/index.html':pathname));
    if(!path.startsWith(root + sep)){res.writeHead(403);res.end();return;}
    const data = await readFile(path);
    res.writeHead(200,{'Content-Type':types[extname(path)]||'application/octet-stream'});res.end(data);
  }catch{res.writeHead(404);res.end('Not found');}
}).listen(8765,'127.0.0.1',()=>process.stdout.write('Local: http://127.0.0.1:8765\n'));

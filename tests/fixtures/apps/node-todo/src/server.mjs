/** HTTP API over the store: what the end-to-end check exercises. */
import {createServer} from 'node:http'
import {createStore} from './todos.mjs'

const store = createStore()
const port = Number(process.env.PORT || 3000)

function send(res, status, body) {
    res.writeHead(status, {'content-type': 'application/json'})
    res.end(JSON.stringify(body))
}

createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/health') return send(res, 200, {ok: true})
    if (req.method === 'GET' && req.url === '/api/todos') return send(res, 200, store.list())
    if (req.method === 'POST' && req.url === '/api/todos') {
        let raw = ''
        req.on('data', (c) => (raw += c))
        req.on('end', () => {
            try {
                send(res, 201, store.add(JSON.parse(raw || '{}').title))
            } catch (e) {
                send(res, 400, {error: e.message})
            }
        })
        return
    }
    send(res, 404, {error: 'not found'})
}).listen(port, '127.0.0.1', () => console.log(`listening on ${port}`))

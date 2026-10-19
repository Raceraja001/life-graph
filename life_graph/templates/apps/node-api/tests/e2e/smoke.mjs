// End-to-end: drive the running server over HTTP, as a client would.
const base = `http://127.0.0.1:${process.env.PORT || 3000}`

async function main() {
    const created = await fetch(`${base}/api/todos`, {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({title: 'ship it'}),
    })
    if (created.status !== 201) throw new Error(`create returned ${created.status}`)
    const empty = await fetch(`${base}/api/todos`, {method: 'POST', body: '{"title": ""}'})
    if (empty.status !== 400) throw new Error(`empty title returned ${empty.status}`)
    const list = await (await fetch(`${base}/api/todos`)).json()
    if (list.length !== 1 || list[0].title !== 'ship it') throw new Error(`unexpected list ${JSON.stringify(list)}`)
    console.log('e2e ok')
}

main().catch((e) => {
    console.error(`e2e failed: ${e.message}`)
    process.exit(1)
})

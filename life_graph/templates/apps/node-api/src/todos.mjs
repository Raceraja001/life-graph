/** An in-memory to-do list: the logic the unit tests cover. */
export function createStore() {
    const items = []
    return {
        add(title) {
            const clean = String(title ?? '').trim()
            if (!clean) throw new Error('title is required')
            const item = {id: items.length + 1, title: clean, done: false}
            items.push(item)
            return item
        },
        complete(id) {
            const item = items.find((t) => t.id === id)
            if (!item) throw new Error(`no todo ${id}`)
            item.done = true
            return item
        },
        list() {
            return items.map((t) => ({...t}))
        },
    }
}

import {describe, expect, test} from 'vitest'
import {createStore} from '../src/todos.mjs'

describe('todos', () => {
    test('adds a todo', () => {
        const s = createStore()
        expect(s.add('  buy milk ')).toEqual({id: 1, title: 'buy milk', done: false})
        expect(s.list()).toHaveLength(1)
    })

    test('rejects an empty title', () => {
        expect(() => createStore().add('   ')).toThrow('title is required')
    })

    test('completes a todo', () => {
        const s = createStore()
        s.add('a')
        expect(s.complete(1).done).toBe(true)
    })
})

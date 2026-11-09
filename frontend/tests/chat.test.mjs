import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
import { createPinia, setActivePinia } from 'pinia'
import { watchEffect, nextTick } from 'vue'

const encode = s => 'data:text/javascript;base64,' + Buffer.from(s).toString('base64')
const compile = s => ts.transpileModule(s, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }}).outputText
const source = readFileSync(new URL('../src/api/chat.ts', import.meta.url), 'utf8')
const api = await import(encode(compile(source.replace("import http from './http'", 'const http = globalThis.testHttp').replace("import { ACCESS_TOKEN_KEY } from './http'", "const ACCESS_TOKEN_KEY = 'token'"))))
globalThis.localStorage = { getItem: () => null, setItem: () => {} }
function response(text) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({ start(c) {
    for (let i = 0; i < bytes.length; i += 7) c.enqueue(bytes.slice(i, i + 7))
    c.close()
  }}))
}
const callbacks = () => ({ onDelta() {}, onCitations() {}, onConversation() {}, onDone() {} })
test('parses backend events across byte boundaries and surfaces errors', async () => {
  let answer = '', id = '', citations = []
  globalThis.fetch = async () => response('event: token\r\ndata: {"content":"你好"}\r\n\r\nevent: citations\ndata: {"items":[{"title":"法条"}]}\n\nevent: done\ndata: {"conversation_id":"abc"}\n\n')
  await api.streamChat({message:'你好'}, {...callbacks(), onDelta: s => answer += s, onConversation: s => id=s, onCitations: s => citations=s})
  assert.equal(answer, '你好'); assert.equal(id, 'abc'); assert.equal(citations.length, 1)
  globalThis.fetch = async () => response('event: error\ndata: {"message":"模型失败"}\n\n')
  await assert.rejects(api.streamChat({message:'x'}, callbacks()), /模型失败/)
})
test('received answer and completion update the reactive message', async () => {
  globalThis.chatApi = api
  const source = readFileSync(new URL('../src/stores/chat.ts', import.meta.url), 'utf8')
  const code = compile(source.replace("from 'vue'", `from '${import.meta.resolve('vue')}'`).replace("from 'pinia'", `from '${import.meta.resolve('pinia')}'`).replace("import { getChatHistory, streamChat } from '../api/chat'", 'const { getChatHistory, streamChat } = globalThis.chatApi'))
  const {useChatStore} = await import(encode(code))
  setActivePinia(createPinia())
  const store = useChatStore()
  let rendered = ''
  const stop = watchEffect(() => { rendered = store.messages.map(m => m.content + ':' + m.streaming).join('|') })
  globalThis.fetch = async () => response('event: token\ndata: {"content":"页面答案"}\n\nevent: done\ndata: {"conversation_id":"reactive-test"}\n\n')
  await store.sendMessage('测试'); await nextTick()
  assert.match(rendered, /页面答案:false/)
  assert.equal(store.streaming, false)
  stop()
})

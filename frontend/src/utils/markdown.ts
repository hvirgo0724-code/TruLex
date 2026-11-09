import { marked } from 'marked'

marked.use({
  gfm: true,
  breaks: true,
})

/**
 * 将 Markdown 文本渲染为 HTML 字符串。
 * 同步解析，返回可直接交给 v-html 的 HTML。
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text, { async: false }) as string
  } catch {
    return escapeHtml(text)
  }
}

/** HTML 转义，防止未渲染时的原始文本注入 */
export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, X, Send, Loader2, Sparkles } from 'lucide-react'
import { chatWithAI } from '../api/client'

const SUGGESTED = [
  'What does the current order imbalance signal?',
  'Explain the current market regime',
  'Is the spread unusually wide right now?',
  'What does RSI tell us here?',
]

function Message({ role, content }) {
  const isUser = role === 'user'
  return (
    <div className={`flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {!isUser && (
        <div className="w-6 h-6 rounded-full bg-brand/20 border border-brand/30 flex items-center justify-center shrink-0 mt-0.5">
          <Bot size={12} className="text-brand" />
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${
          isUser
            ? 'bg-brand/20 border border-brand/30 text-slate-200 ml-auto'
            : 'bg-white/5 border border-white/10 text-slate-300'
        }`}
      >
        {content}
      </div>
    </div>
  )
}

export default function ChatWidget() {
  const [open, setOpen]         = useState(false)
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I\'m FlashLedger AI powered by Groq + Llama 3.3. Ask me anything about the current market microstructure.' }
  ])
  const [input,    setInput]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const bottomRef               = useRef(null)

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const send = async (text) => {
    const msg = text ?? input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: msg }])
    setLoading(true)
    try {
      const { reply } = await chatWithAI(msg)
      setMessages((m) => [...m, { role: 'assistant', content: reply }])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', content: 'Could not reach the AI — check your GROQ_API_KEY.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Floating trigger button */}
      <motion.button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-brand shadow-lg shadow-brand/30 flex items-center justify-center hover:scale-110 transition-transform"
        whileTap={{ scale: 0.95 }}
        title="Ask FlashLedger AI"
      >
        <AnimatePresence mode="wait">
          {open
            ? <motion.span key="x"   initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}><X    size={20} className="text-white" /></motion.span>
            : <motion.span key="bot" initial={{ rotate:  90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}><Bot  size={20} className="text-white" /></motion.span>
          }
        </AnimatePresence>
      </motion.button>

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.95 }}
            animate={{ opacity: 1, y: 0,  scale: 1    }}
            exit={{    opacity: 0, y: 24, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="fixed bottom-24 right-6 z-50 w-[360px] max-h-[520px] flex flex-col rounded-2xl border border-white/10 bg-navy-900 shadow-2xl shadow-black/60 overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/5 shrink-0">
              <div className="w-6 h-6 rounded-full bg-brand/20 border border-brand/30 flex items-center justify-center">
                <Bot size={13} className="text-brand" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-slate-200 leading-none">FlashLedger AI</div>
                <div className="text-[10px] text-slate-500 mt-0.5 flex items-center gap-1">
                  <Sparkles size={9} className="text-gold" />
                  Groq · Llama 3.3 70B
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3 min-h-0">
              {messages.map((m, i) => <Message key={i} {...m} />)}
              {loading && (
                <div className="flex gap-2">
                  <div className="w-6 h-6 rounded-full bg-brand/20 border border-brand/30 flex items-center justify-center shrink-0">
                    <Bot size={12} className="text-brand" />
                  </div>
                  <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-2">
                    <Loader2 size={14} className="text-brand animate-spin" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Suggested prompts (only when no conversation yet) */}
            {messages.length === 1 && (
              <div className="px-4 pb-2 flex flex-wrap gap-1.5 shrink-0">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-[10px] px-2.5 py-1 rounded-full border border-brand/30 bg-brand/10 text-brand hover:bg-brand/20 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Input */}
            <div className="px-4 py-3 border-t border-white/10 bg-white/5 shrink-0">
              <div className="flex gap-2">
                <input
                  className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand/50 transition-colors"
                  placeholder="Ask about market conditions…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
                  disabled={loading}
                  maxLength={1000}
                />
                <button
                  onClick={() => send()}
                  disabled={!input.trim() || loading}
                  className="w-8 h-8 flex items-center justify-center rounded-xl bg-brand hover:bg-brand/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <Send size={13} className="text-white" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

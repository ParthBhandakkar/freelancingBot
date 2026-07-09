import { useState, useEffect, useCallback, createContext, useContext } from 'react'

const ToastContext = createContext()

export function useToast() {
  return useContext(ToastContext)
}

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, duration)
    }
    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const success = useCallback((msg, dur) => addToast(msg, 'success', dur), [addToast])
  const error = useCallback((msg, dur) => addToast(msg, 'error', dur), [addToast])
  const info = useCallback((msg, dur) => addToast(msg, 'info', dur), [addToast])

  const colors = {
    success: 'bg-green-600 text-white',
    error: 'bg-red-600 text-white',
    info: 'bg-blue-600 text-white',
  }

  return (
    <ToastContext.Provider value={{ addToast, removeToast, success, error, info }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2 animate-slide-up ${colors[t.type] || colors.info}`}
          >
            <span className="flex-1">{t.message}</span>
            <button onClick={() => removeToast(t.id)} className="text-white/80 hover:text-white text-lg leading-none">&times;</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

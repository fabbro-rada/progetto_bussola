import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type TextSize = 'normal' | 'large' | 'xlarge'

const SCALE: Record<TextSize, string> = { normal: '1', large: '1.25', xlarge: '1.5' }

interface TextSizeContextValue {
  size: TextSize
  setSize: (s: TextSize) => void
}

const TextSizeContext = createContext<TextSizeContextValue | null>(null)

export function TextSizeProvider({ children }: { children: ReactNode }) {
  const [size, setSize] = useState<TextSize>('normal')
  useEffect(() => {
    document.documentElement.style.setProperty('--text-scale', SCALE[size])
  }, [size])
  return <TextSizeContext.Provider value={{ size, setSize }}>{children}</TextSizeContext.Provider>
}

export function useTextSize(): TextSizeContextValue {
  const ctx = useContext(TextSizeContext)
  if (!ctx) throw new Error('useTextSize must be used within a TextSizeProvider')
  return ctx
}

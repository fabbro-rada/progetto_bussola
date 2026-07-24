import { type ReactNode } from 'react'

export function Notice({
  tone,
  text,
  children,
}: {
  tone: 'warn' | 'info' | 'success' | 'error'
  text: string
  children?: ReactNode
}) {
  return (
    <div className={`notice notice-${tone}`}>
      <p>{text}</p>
      {children}
    </div>
  )
}

import { type ButtonHTMLAttributes } from 'react'

type Variant = 'confirm' | 'secondary' | 'danger'

export function BigButton({
  variant = 'confirm',
  className,
  ...props
}: { variant?: Variant } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`big-button big-${variant} ${className ?? ''}`.trim()} {...props} />
}

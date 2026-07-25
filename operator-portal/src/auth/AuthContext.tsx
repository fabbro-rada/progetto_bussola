import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { operatorClient } from '../api/operatorClient'
import { clearToken, getToken, setToken } from './session'
import type { ChangeResult, LoginResult, Operator, OperatorClient } from '../types'

interface AuthValue {
  operator: Operator | null
  loading: boolean
  mustChangePassword: boolean
  login(username: string, password: string): Promise<LoginResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  clearMustChangePassword(): void
  onUnauthorized(): void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ client = operatorClient, children }: { client?: OperatorClient; children: ReactNode }) {
  const [operator, setOperator] = useState<Operator | null>(null)
  const [mustChangePassword, setMcp] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    let active = true
    void client.me().then((r) => {
      if (!active) return
      if (r.status === 'ok') {
        setOperator(r.operator)
        setMcp(r.operator.must_change_password)
      } else {
        clearToken()
        setOperator(null)
      }
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [client])

  const login = useCallback(
    async (username: string, password: string): Promise<LoginResult> => {
      const r = await client.login(username, password)
      if (r.status === 'ok') {
        setToken(r.token)
        setOperator(r.operator)
        setMcp(r.mustChangePassword)
      }
      return r
    },
    [client],
  )

  const logout = useCallback(async () => {
    await client.logout()
    clearToken()
    setOperator(null)
    setMcp(false)
  }, [client])

  const changePassword = useCallback(
    (oldPassword: string, newPassword: string) => client.changePassword(oldPassword, newPassword),
    [client],
  )

  const clearMustChangePassword = useCallback(() => setMcp(false), [])
  const onUnauthorized = useCallback(() => {
    clearToken()
    setOperator(null)
    setMcp(false)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        operator,
        loading,
        mustChangePassword,
        login,
        logout,
        changePassword,
        clearMustChangePassword,
        onUnauthorized,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}

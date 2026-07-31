import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { operatorClient } from '../api/operatorClient'
import { clearToken, getToken, setToken } from './session'
import type { ChangeResult, LoginResult, Operator, OperatorClient } from '../types'

interface AuthValue {
  operator: Operator | null
  loading: boolean
  mustChangePassword: boolean
  sessionExpired: boolean
  passwordChanged: boolean
  client: OperatorClient
  login(username: string, password: string): Promise<LoginResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
  onPasswordChanged(): void
  clearPasswordChanged(): void
  clearSessionExpired(): void
  onUnauthorized(): void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ client = operatorClient, children }: { client?: OperatorClient; children: ReactNode }) {
  const [operator, setOperator] = useState<Operator | null>(null)
  const [mustChangePassword, setMcp] = useState(false)
  const [loading, setLoading] = useState(true)
  const [sessionExpired, setSessionExpired] = useState(false)
  const [passwordChanged, setPasswordChanged] = useState(false)

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
      } else if (r.status === 'unauthorized') {
        clearToken()
        setOperator(null)
        setSessionExpired(true)
      } else {
        // 'error' (network/5xx): transient — do NOT clear the token, do NOT flag expired
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
        setSessionExpired(false)
        setPasswordChanged(false)
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

  const onPasswordChanged = useCallback(() => {
    // change_password revokes ALL of the operator's sessions server-side (§7.2),
    // so the current token is already dead. Sign out locally and let the caller
    // route back to /login, instead of navigating on with a token that 401s.
    clearToken()
    setOperator(null)
    setMcp(false)
    setPasswordChanged(true)
  }, [])
  const clearPasswordChanged = useCallback(() => setPasswordChanged(false), [])
  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])
  const onUnauthorized = useCallback(() => {
    clearToken()
    setOperator(null)
    setMcp(false)
    setSessionExpired(true)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        operator,
        loading,
        mustChangePassword,
        sessionExpired,
        passwordChanged,
        client,
        login,
        logout,
        changePassword,
        onPasswordChanged,
        clearPasswordChanged,
        clearSessionExpired,
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

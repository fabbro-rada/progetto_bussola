export type Role = 'operator' | 'supervisor' | 'admin' | 'auditor'

export interface Operator {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
}

export type LoginResult =
  | { status: 'ok'; token: string; operator: Operator; mustChangePassword: boolean }
  | { status: 'invalid' }
  | { status: 'error' }

export type MeResult = { status: 'ok'; operator: Operator } | { status: 'unauthorized' } | { status: 'error' }

export type ChangeResult = { status: 'ok' } | { status: 'unauthorized' } | { status: 'error' }

export interface OperatorClient {
  login(username: string, password: string): Promise<LoginResult>
  me(): Promise<MeResult>
  logout(): Promise<void>
  changePassword(oldPassword: string, newPassword: string): Promise<ChangeResult>
}

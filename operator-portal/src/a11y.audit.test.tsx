import { screen } from '@testing-library/react'
import { test, vi, afterEach } from 'vitest'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './test/utils'
import { expectNoA11yViolations } from './test/axe'
import { makeFakeClient, operatorWith, ADMIN, MATCH } from './test/fakeClient'
import { setToken } from './auth/session'

import { MetricsPanel } from './screens/metrics/MetricsPanel'
import { ReportPanel } from './screens/report/ReportPanel'
import { OperatorActivityPanel } from './screens/activity/OperatorActivityPanel'
import { SystemConfigPanel } from './screens/system/SystemConfigPanel'
import { AuditLog } from './screens/audit/AuditLog'
import { ExportRequests } from './screens/exports/ExportRequests'
import { ExportApprovals } from './screens/exports/ExportApprovals'
import { JobRequestList } from './screens/jobRequests/JobRequestList'
import { JobRequestDetail } from './screens/jobRequests/JobRequestDetail'
import { ProfileSearch } from './screens/profiles/ProfileSearch'
import { ProfileDetail } from './screens/profiles/ProfileDetail'
import { FollowupTokenModal } from './screens/profiles/FollowupTokenModal'
import { OperatorList } from './screens/operators/OperatorList'

import { Login } from './screens/Login'
import { ChangePassword } from './screens/ChangePassword'
import { JobRequestCreate } from './screens/jobRequests/JobRequestCreate'
import { MatchResults } from './screens/jobRequests/MatchResults'
import { NewExportForm } from './screens/exports/NewExportForm'
import { DenyDialog } from './screens/exports/DenyDialog'
import { CreateOperatorForm } from './screens/operators/CreateOperatorForm'
import { ConfirmDialog } from './screens/operators/ConfirmDialog'
import { TempPasswordModal } from './screens/operators/TempPasswordModal'
import { SkillBadge } from './screens/profiles/SkillBadge'
import { Home } from './screens/Home'
import { Unauthorized } from './screens/Unauthorized'

const noop = () => {}

afterEach(() => sessionStorage.clear())

// Every operator-portal screen and shared component is rendered in its normal
// loaded (success) state and checked for component-level a11y violations.
// Data-driven panels fetch on mount (§7.2), so each is given a fake client
// scoped to the role that can see it and awaited to its loaded content before
// axe runs — auditing a spinner would tell us nothing.

test('MetricsPanel (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/metrics" element={<MetricsPanel />} />
    </Routes>,
    { client, route: '/metrics' },
  )
  await screen.findByText('60%')
  await expectNoA11yViolations(container)
})

test('ReportPanel (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/report" element={<ReportPanel />} />
    </Routes>,
    { client, route: '/report' },
  )
  await screen.findByText('60%')
  await expectNoA11yViolations(container)
})

test('OperatorActivityPanel (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/activity" element={<OperatorActivityPanel />} />
    </Routes>,
    { client, route: '/activity' },
  )
  await screen.findByText('m.rossi')
  await expectNoA11yViolations(container)
})

test('SystemConfigPanel (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'admin' }) } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/config" element={<SystemConfigPanel />} />
    </Routes>,
    { client, route: '/config' },
  )
  await screen.findByText('qwen2.5-7b-instruct')
  await expectNoA11yViolations(container)
})

test('AuditLog (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'auditor' }) } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/audit" element={<AuditLog />} />
    </Routes>,
    { client, route: '/audit' },
  )
  await screen.findByText('profile_viewed')
  await expectNoA11yViolations(container)
})

test('ExportRequests (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/export" element={<ExportRequests />} />
    </Routes>,
    { client, route: '/export' },
  )
  await screen.findByText('cucina')
  await expectNoA11yViolations(container)
})

test('ExportApprovals (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith({ role: 'supervisor' }) } })
  const { container } = renderWithProviders(<ExportApprovals />, { client, route: '/export-approvals' })
  await screen.findByText('m.rossi')
  await expectNoA11yViolations(container)
})

test('JobRequestList (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/job-requests" element={<JobRequestList />} />
    </Routes>,
    { client, route: '/job-requests' },
  )
  await screen.findByText('Aiuto cuoco')
  await expectNoA11yViolations(container)
})

test('JobRequestDetail (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/job-requests/:id" element={<JobRequestDetail />} />
    </Routes>,
    { client, route: '/job-requests/7' },
  )
  await screen.findByText('Aiuto cuoco')
  await expectNoA11yViolations(container)
})

test('ProfileSearch (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/profiles" element={<ProfileSearch />} />
    </Routes>,
    { client, route: '/profiles' },
  )
  await screen.findByRole('link', { name: 'P-4F2A' })
  await expectNoA11yViolations(container)
})

test('ProfileDetail (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/profiles/:pseudonym" element={<ProfileDetail />} />
    </Routes>,
    { client, route: '/profiles/P-4F2A' },
  )
  await screen.findByText('P-4F2A')
  await expectNoA11yViolations(container)
})

test('OperatorList (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: ADMIN } })
  const { container } = renderWithProviders(<OperatorList />, { client, route: '/operators' })
  await screen.findByText('Maria Rossi')
  await expectNoA11yViolations(container)
})

test('Home (loaded) has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>,
    { client, route: '/' },
  )
  await screen.findByText('Benvenuto/a, M. Rossi')
  await expectNoA11yViolations(container)
})

test('Unauthorized has no a11y violations', async () => {
  const { container } = renderWithProviders(<Unauthorized />)
  await screen.findByRole('alert')
  await expectNoA11yViolations(container)
})

test('Login has no a11y violations', async () => {
  const client = makeFakeClient({})
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/login" element={<Login />} />
    </Routes>,
    { client, route: '/login' },
  )
  await screen.findByLabelText('Nome utente')
  await expectNoA11yViolations(container)
})

test('ChangePassword has no a11y violations', async () => {
  const client = makeFakeClient({})
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/change-password" element={<ChangePassword />} />
    </Routes>,
    { client, route: '/change-password' },
  )
  await screen.findByLabelText('Password attuale')
  await expectNoA11yViolations(container)
})

test('JobRequestCreate has no a11y violations', async () => {
  setToken('tok')
  const client = makeFakeClient({ me: { status: 'ok', operator: operatorWith() } })
  const { container } = renderWithProviders(
    <Routes>
      <Route path="/job-requests/new" element={<JobRequestCreate />} />
    </Routes>,
    { client, route: '/job-requests/new' },
  )
  await screen.findByLabelText('Titolo')
  await expectNoA11yViolations(container)
})

test('MatchResults has no a11y violations', async () => {
  const { container } = renderWithProviders(<MatchResults results={[MATCH]} />)
  await screen.findByText('P-4F2A')
  await expectNoA11yViolations(container)
})

test('NewExportForm has no a11y violations', async () => {
  const { container } = renderWithProviders(<NewExportForm onSubmit={noop} onCancel={noop} busy={false} error="" />)
  await screen.findByLabelText('Motivo / destinatario')
  await expectNoA11yViolations(container)
})

test('DenyDialog has no a11y violations', async () => {
  const { container } = renderWithProviders(<DenyDialog title="Nega la richiesta di «m.rossi»" onConfirm={noop} onCancel={noop} />)
  await screen.findByRole('dialog')
  await expectNoA11yViolations(container)
})

test('CreateOperatorForm has no a11y violations', async () => {
  const { container } = renderWithProviders(<CreateOperatorForm onSubmit={noop} onCancel={noop} busy={false} error="" />)
  await screen.findByLabelText('Nome utente')
  await expectNoA11yViolations(container)
})

test('ConfirmDialog has no a11y violations', async () => {
  const { container } = renderWithProviders(
    <ConfirmDialog message="Disabilitare «x»?" confirmLabel="Conferma" onConfirm={noop} onCancel={noop} />,
  )
  await screen.findByText('Disabilitare «x»?')
  await expectNoA11yViolations(container)
})

test('TempPasswordModal has no a11y violations', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  const { container } = renderWithProviders(
    <TempPasswordModal password="7Kq9-mZ2t-Rf4x" subtitle="Operatore «x» creato." onClose={noop} copy={copy} />,
  )
  await screen.findByText('7Kq9-mZ2t-Rf4x')
  await expectNoA11yViolations(container)
})

test('FollowupTokenModal has no a11y violations', async () => {
  const copy = vi.fn().mockResolvedValue(undefined)
  const { container } = renderWithProviders(
    <FollowupTokenModal token="FUP-9K2M-7QRT" subtitle="Follow-up per «P-4F2A»." onClose={noop} copy={copy} />,
  )
  await screen.findByText('FUP-9K2M-7QRT')
  await expectNoA11yViolations(container)
})

test('SkillBadge has no a11y violations', async () => {
  const { container } = renderWithProviders(
    <>
      <SkillBadge grade="certified" />
      <SkillBadge grade="demonstrated" />
      <SkillBadge grade="stated" />
    </>,
  )
  await screen.findByText(/Certificata/)
  await expectNoA11yViolations(container)
})

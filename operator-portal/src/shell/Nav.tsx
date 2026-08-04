import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { NAV_BY_ROLE } from '../rbac/nav'

export function Nav() {
  const { t } = useTranslation()
  const { operator } = useAuth()
  if (!operator) return null
  const items = NAV_BY_ROLE[operator.role]
  return (
    <nav className="nav" aria-label={t('nav.ariaLabel')}>
      <ul>
        {items.map((item) => (
          <li key={item.path}>
            {item.built ? (
              <NavLink
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                to={item.path}
              >
                {t(item.labelKey)}
              </NavLink>
            ) : (
              <span className="nav-item disabled" aria-disabled="true">
                {t(item.labelKey)} <em className="coming">({t('common.comingSoon')})</em>
              </span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  )
}

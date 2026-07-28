import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useFetchOnMount } from '../../hooks/useFetchOnMount'

export function OperatorActivityPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const fetchActivity = useCallback(() => client.getOperatorActivity(), [client])
  const { data: activity, error } = useFetchOnMount(fetchActivity, (r) => r.activity)

  return (
    <div className="activity">
      <h1>{t('activity.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {activity === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        activity &&
        (activity.length === 0 ? (
          <p>{t('activity.empty')}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t('activity.colOperator')}</th>
                <th>{t('activity.colProfilesViewed')}</th>
                <th>{t('activity.colSearches')}</th>
                <th>{t('activity.colMatchings')}</th>
                <th>{t('activity.colExports')}</th>
                <th>{t('activity.colLastActive')}</th>
              </tr>
            </thead>
            <tbody>
              {activity.map((a) => (
                <tr key={a.actor}>
                  <td>{a.actor}</td>
                  <td>{a.profiles_viewed}</td>
                  <td>{a.profiles_searched}</td>
                  <td>{a.matchings_run}</td>
                  <td>{a.exports_requested}/{a.exports_downloaded}</td>
                  <td>{a.last_active.replace('T', ' ').slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))
      )}
    </div>
  )
}

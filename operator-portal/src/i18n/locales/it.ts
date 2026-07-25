export const it = {
  common: { loading: 'Caricamento…', comingSoon: 'in arrivo' },
  login: {
    title: 'Portale operatore',
    username: 'Nome utente',
    password: 'Password',
    submit: 'Entra',
  },
  changePassword: {
    title: 'Cambia la password',
    intro: 'Per continuare devi impostare una nuova password.',
    old: 'Password attuale',
    new: 'Nuova password',
    submit: 'Salva la nuova password',
  },
  home: { welcome: 'Benvenuto/a, {{name}}' },
  shell: {
    logout: 'Esci',
    role: { operator: 'Operatore', supervisor: 'Supervisore', admin: 'Amministratore', auditor: 'Auditor' },
  },
  nav: {
    ariaLabel: 'Sezioni',
    jobRequests: 'Richieste di lavoro',
    profiles: 'Profili',
    export: 'Export',
    metrics: 'Metriche',
    activity: 'Attività operatori',
    operators: 'Gestione utenze',
    config: 'Configurazione',
    audit: 'Log di audit',
  },
  unauthorized: { text: 'Non hai i permessi per questa sezione.' },
  errors: {
    invalidCredentials: 'Credenziali non valide.',
    sessionExpired: 'Sessione scaduta. Accedi di nuovo.',
    generic: 'Si è verificato un errore. Riprova.',
  },
}

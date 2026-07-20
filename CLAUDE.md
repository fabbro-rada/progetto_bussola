# CLAUDE.md — Assistente per la profilazione lavorativa delle persone detenute

**Progetto «Bussola»** · Progetto pilota — Casa Circondariale di Monza · *Documento-nucleo funzionale*

---

## 0. Come usare e mantenere questo documento

Questo è il **documento-nucleo** del progetto: definisce **cosa** costruiamo e **perché**. È la fonte di verità sulle intenzioni, i vincoli e i limiti del sistema.

Non è una specifica tecnica. Non descrive **come** implementare: qui non trovi librerie, comandi, schema del database o configurazioni. Il "come" vive in un documento separato, vivo, che può evolvere liberamente (vedi §12).

**Regola del blocco (governance del nucleo).**
Le sezioni da §1 a §11 sono **protette**. Se durante lo sviluppo emerge la necessità di modificare un concetto qui espresso — la missione, un vincolo, una linea rossa, il modello del profilo, i ruoli, le funzionalità, l'ambito, i criteri di successo — l'assistente di sviluppo:

1. **si ferma**, senza toccare nulla;
2. **spiega** perché il cambiamento sarebbe necessario e cosa comporta;
3. **chiede conferma esplicita** all'utente;
4. solo dopo l'approvazione, **aggiorna** questo documento nello stesso passaggio.

Nessuna modifica silenziosa al nucleo. Se un'esigenza tecnica sembra contraddire il nucleo, la contraddizione va sollevata, non aggirata.

---

## 1. Missione e perché

**Missione.** Realizzare un assistente conversazionale, funzionante interamente in locale, che aiuti ogni persona detenuta a costruire un **profilo lavorativo realistico** — esperienze, competenze, aspirazioni, bisogni formativi — e che permetta agli operatori di **orientarla e collegarla a opportunità di lavoro reali**, dentro e fuori dal carcere.

**Perché.** Il legame tra lavoro e riduzione della recidiva è consolidato e basato su dati: chi durante la detenzione svolge un'esperienza lavorativa significativa ha molte meno probabilità di tornare a delinquere. Oggi il tasso di recidiva è intorno al 70%. L'ostacolo principale non è la mancanza di volontà, ma la **difficoltà di conoscere davvero la persona** sul piano lavorativo — potenzialità, esperienze, aspirazioni — in un contesto con personale insufficiente. Il sistema serve a colmare questa distanza in modo scalabile e replicabile.

A Monza il bisogno è ancora più acuto: sovraffollamento intorno al 160% e una popolazione straniera vicina al 50%. Per questo la **multilingua e la voce non sono un abbellimento, ma un requisito funzionale**: senza di esse metà delle persone resterebbe di fatto esclusa.

**Cosa rende il progetto diverso.** È un uso dell'intelligenza artificiale nelle carceri finora inedito: mirato al **reinserimento sociale attraverso il lavoro**, non al controllo, alla sorveglianza o alla previsione del rischio. Questa differenza non è un dettaglio: è l'identità del progetto.

---

## 2. Cosa NON è — le linee rosse

**Questo è il requisito funzionale più importante.** Definisce ciò che il sistema non deve poter fare, in nessuna circostanza.

- **Non è uno strumento di sorveglianza, controllo o disciplina.** Non stima pericolosità, non calcola rischi di recidiva, non produce punteggi sulle persone. Non è un sistema di lettura del comportamento.
- **Il profilo è soltanto un profilo lavorativo.** Contiene esperienze, competenze, aspirazioni e bisogni formativi. Non contiene informazioni su reati, salute, vita familiare o qualunque dato non pertinente al lavoro (vedi §5).
- **I dati non possono essere riusati per finalità di sicurezza, disciplina, valutazione o profilazione della persona.** L'accesso è vincolato allo scopo: orientamento e matching lavorativo.
- **Il sistema resta nel proprio ambito.** Risponde solo su lavoro, formazione e orientamento. Ogni richiesta fuori contesto — dati di terzi, contenuti vietati, temi non pertinenti — viene rifiutata, in ingresso e in uscita.
- **Il sistema non giudica.** Dialoga in modo accogliente e non stigmatizzante, con chiunque, a prescindere dal passato.

Se una funzionalità proposta rischia di violare una di queste linee, va fermata e discussa (§0).

---

## 3. Vincoli non negoziabili

- **Locale / on-premise.** I modelli e i dati vivono su infrastruttura interna. Nessun dato esce verso terze parti. Nessun servizio cloud a pagamento, nessuna API esterna per l'inferenza.
- **Open source.** L'intero stack — dialogo, voce, dati, portale — usa componenti a licenza aperta e permissiva.
- **Budget nullo.** Nessun costo di licenza o di servizio. Il prototipo deve girare su hardware già disponibile.
- **Privacy by design.** Minimizzazione, pseudonimizzazione, segregazione, cifratura, controlli di accesso e audit sono parte della progettazione, non aggiunte finali.
- **Prima il testo, la voce come potenziamento, degrado elegante.** L'esperienza testuale deve sempre funzionare ed essere reattiva. La voce arricchisce l'interazione; se non è disponibile o è lenta, il sistema ripiega con naturalezza sul testo, senza mai bloccarsi.
- **Prevenzione dell'uso scorretto.** Controllo dell'ambito, azioni consentite solo tra quelle previste, input strutturati, logging e flussi autorizzativi per ogni condivisione verso l'esterno.

---

## 4. Carta dei principi (etica e dignità)

Il sistema si rivolge a persone in una condizione di vulnerabilità. Questi principi vengono prima di ogni funzionalità.

- **Volontarietà e consenso informato.** La partecipazione è libera. Prima di iniziare, la persona capisce a cosa serve il colloquio, quali dati vengono raccolti e come vengono usati. Può interrompere in qualsiasi momento.
- **Non coercizione.** Il sistema non fa pressioni e non insiste su temi delicati; offre sempre alternative neutrali.
- **Non giudizio.** Il tono è positivo e incoraggiante. L'obiettivo è far emergere le potenzialità, non evidenziare le mancanze.
- **Minimizzazione dei dati.** Si chiede solo ciò che serve all'orientamento e al matching. Nulla di più.
- **Spiegabilità.** Ogni suggerimento agli operatori (un abbinamento, un percorso formativo) è accompagnato dal *perché*, in forma comprensibile.
- **Accessibilità e inclusione.** Font grandi, buon contrasto, lettura vocale, testo semplificato, multilingua. Il sistema deve essere usabile anche da chi ha bassa alfabetizzazione o non parla italiano.

---

## 5. Il modello concettuale del profilo

Il profilo è la struttura dati centrale. È **minimo per costruzione**: è proprio questa minimalità a rendere sicuro l'accesso degli operatori (§6), perché non c'è materiale sensibile da poter usare in modo improprio.

**Cosa contiene il profilo (concettualmente):**

- un identificativo interno **pseudonimizzato**, separato dai dati anagrafici;
- lingue conosciute e livello di alfabetizzazione digitale;
- competenze tecniche e trasversali, con un'indicazione del grado di evidenza;
- esperienze lavorative pregresse (ruolo, settore, durata);
- preferenze e aspirazioni (ambiti, disponibilità, vincoli);
- formazione desiderata;
- eventuali note operative, solo se necessarie e per categorie predefinite.

**Cosa il profilo NON deve mai contenere:**

- informazioni sui reati, sulla posizione giuridica o sulla pericolosità;
- dati sanitari;
- dati sensibili sulla vita familiare o personale non pertinenti al lavoro;
- inferenze o valutazioni sulla persona che esulino dall'ambito lavorativo.

**Realismo e conferma: valida la persona, non l'operatore.**
Il valore del profilo dipende dalla sua aderenza alla realtà. Ma il personale del carcere è la risorsa più scarsa: un sistema che chiedesse agli operatori di verificare ogni profilo non risolverebbe il problema, lo sposterebbe soltanto. Per questo la validazione avviene **durante il colloquio, con la persona stessa**:

- il sistema **riepiloga** ciò che ha compreso — al termine di ogni sezione e alla fine del colloquio — e chiede alla persona di **confermare o correggere**;
- quando emerge un'**incongruenza** (una durata che non torna, una competenza in contrasto con le esperienze raccontate), il sistema **non accusa e non giudica**: pone una domanda di chiarimento gentile e chiede conferma.

Ne risulta un profilo realistico che **non consuma tempo degli operatori**: questi ricevono profili già confermati dalla persona e si dedicano al loro compito — le richieste delle aziende e il matching. Il sistema, da solo, non decide cosa registrare come definitivo: lo registra perché la persona lo ha confermato.

---

## 6. Ruoli e accesso — chi fa cosa, e perché

L'accesso al sistema è **vincolato allo scopo** (orientamento e matching lavorativo). Ogni ruolo opera a **privilegio minimo** e ogni operazione rilevante è registrata nel log di audit (§7.3).

- **Operatore — fa funzionare il reinserimento.** Inserisce le richieste di lavoro delle aziende, avvia e legge i matching, consulta i profili lavorativi per abbinarli alle posizioni. Può essere un **agente della Polizia Penitenziaria** con utenza autorizzata rilasciata dalla Direzione, oppure una figura dell'area trattamentale o dell'ente del terzo settore. Non recupera informazioni personali: nel profilo, per costruzione, non ce ne sono.
- **Supervisore — coordina e ha la visione d'insieme.** Vede lo stato di avanzamento, le metriche di qualità e l'attività degli operatori; organizza il lavoro. Non è un validatore dei singoli dati. Tipicamente la Direzione o il responsabile del progetto.
- **Amministratore — gestisce la piattaforma, non il merito.** Crea e disattiva le utenze, configura il sistema, ne cura il funzionamento. È un ruolo tecnico-gestionale, distinto dall'uso dei profili per il lavoro.
- **Auditor — garantisce il corretto uso.** Accede in **sola lettura** al log di audit per verificare chi ha fatto cosa e quando. Non modifica nulla e non partecipa all'operatività. È la garanzia concreta contro il riuso improprio dei dati.

La linea rossa del §2 vale per tutti i ruoli, senza eccezioni.

---

## 7. Funzionalità del sistema

Le funzionalità sono descritte a livello funzionale — **cosa** fanno e **perché** — non tecnico. Salvo dove indicato come **Fase 2**, tutto appartiene al prototipo (Fase 1).

### 7.1 Esperienza della persona detenuta

- **Onboarding e consenso informato.** All'avvio il sistema spiega in modo semplice a cosa serve, quali dati raccoglie, come li usa, e che la partecipazione è libera e interrompibile in ogni momento. *Perché:* senza fiducia e volontarietà non si ottengono dati sinceri.
- **Scelta della lingua.** La persona sceglie la lingua tra le cinque supportate; l'intero colloquio prosegue in quella lingua. *Perché:* quasi metà della popolazione è straniera; la lingua è la prima barriera da abbattere.
- **Colloquio guidato a tappe.** Un percorso condotto per sezioni (competenze, esperienze, aspirazioni, vincoli, preferenze), con domande brevi e opzioni rapide. È il sistema a condurre; la persona non deve sapere "cosa dire". *Perché:* semplicità, meno ansia, dati raccolti in modo ordinato.
- **Interazione vocale.** La persona può parlare invece di scrivere e ascoltare invece di leggere. *Perché:* accessibilità per chi ha bassa alfabetizzazione; interazione più naturale.
- **Ripiego elegante tra voce e testo.** Se la voce non è disponibile o è lenta, si passa al testo senza interruzioni. *Perché:* il colloquio non deve mai bloccarsi.
- **Riepilogo e conferma dalla persona.** Alla fine di ogni sezione e del colloquio, il sistema riassume ciò che ha capito e chiede di confermare o correggere. *Perché:* è il meccanismo che rende il profilo realistico senza impegnare il personale (§5).
- **Chiarimento delle incongruenze.** Quando un dato non torna, il sistema pone una domanda gentile e chiede conferma, senza giudicare. *Perché:* affidabilità del profilo.
- **Ambito bloccato.** Il sistema parla solo di lavoro, formazione e orientamento; ogni altra richiesta è rifiutata con garbo. *Perché:* linea rossa e prevenzione degli abusi.
- **Accessibilità.** Font grandi, buon contrasto, testo semplificato, lettura vocale e un comando immediato per fermare la sessione. *Perché:* dignità e inclusione.
- **Postazione bloccata (kiosk).** Sul dispositivo è utilizzabile solo l'app: niente navigazione o uso libero. *Perché:* sicurezza e prevenzione di usi impropri.

### 7.2 Portale dell'operatore

- **Accesso per ruoli.** Ingresso con utenza autorizzata dalla Direzione, con permessi secondo il ruolo (§6). *Perché:* accesso vincolato allo scopo e tracciabile.
- **Inserimento delle richieste di lavoro.** L'operatore inserisce le posizioni offerte dalle aziende: competenze richieste, vincoli logistici e legali, prerequisiti formativi. *Perché:* alimentare il matching con il fabbisogno reale.
- **Matching spiegabile.** Per ogni abbinamento proposto, il sistema mostra il *perché* (le caratteristiche che pesano) e i **gap formativi** con i percorsi consigliati. *Perché:* decisioni comprensibili e orientamento formativo integrato; mai una "scatola nera".
- **Consultazione dei profili.** Ricerca e filtri (competenze, lingue, esperienza) sui profili lavorativi. *Perché:* trovare le persone adatte alle posizioni.
- **Metriche minime di qualità.** Numero di colloqui completati, completezza dei profili. *Perché:* capire se il sistema funziona e preparare la base per il report.
- **Esportazione di base.** Estrazione controllata di dati ed esiti. *Perché:* portare fuori i risultati per il raccordo con le aziende.
- **(Fase 2) Colloqui di follow-up.** Colloqui successivi per aggiornare il profilo in base all'esperienza lavorativa in corso.
- **(Fase 2) Esportazione avanzata e reportistica** aggregata e anonima, a supporto del report finale.

### 7.3 Dati, integrità e sicurezza (trasversali)

- **Estrazione strutturata validata.** Dalla conversazione il sistema ricava dati strutturati conformi a uno schema definito e scarta ciò che non è ammesso. *Perché:* dati puliti e coerenti, nessun campo fuori posto.
- **Profilo minimo per costruzione.** Lo schema ammette solo dati lavorativi: per costruzione non può contenere reati, salute o dati familiari sensibili. *Perché:* è ciò che rende sicuro l'accesso degli operatori (§2).
- **Pseudonimizzazione e segregazione.** Identificativo interno separato dall'anagrafica; profili separati dai registri delle conversazioni. *Perché:* privacy by design.
- **Protezione dei dati.** Dati protetti sia quando sono conservati sia quando viaggiano nella rete interna. *Perché:* riservatezza.
- **Filtro dei dati personali in uscita.** Prima di mostrare o salvare, il sistema rileva ed elimina eventuali dati personali non pertinenti. *Perché:* nessuna fuoriuscita; il modello non decide da solo cosa esporre.
- **Registro di audit immutabile.** Traccia, in sola aggiunta, chi ha fatto cosa e quando. *Perché:* accountability e garanzia contro il riuso improprio.
- **Autorizzazione per le condivisioni esterne.** Ogni esportazione o condivisione verso l'esterno passa da un'approvazione. *Perché:* controllo sui dati che escono.
- **Resistenza agli abusi.** Il sistema resiste ai tentativi di manipolazione e di estrazione dei dati e può eseguire solo azioni previste. *Perché:* integrità e sicurezza.

**Escluso dal perimetro** (per scelta): l'orientamento *autonomo* alla ricerca del lavoro (portali pubblici, sportelli, centri per l'impiego). Il matching già offre l'orientamento formativo; questa funzione più ampia resta un'eventuale estensione futura, fuori dal progetto attuale.

---

## 8. Ambito: Fase 1 e Fase 2

**Fase 1 — il prototipo funzionante.** Tutte le funzionalità del §7, tranne quelle marcate Fase 2. In sintesi: ciclo centrale completo (colloquio → estrazione validata → guardrail → portale operatori con matching spiegabile), voce e multilingua nelle cinque lingue, esportazione di base.

**Fase 2 — evoluzioni previste.** Colloqui di follow-up e esportazione avanzata con reportistica aggregata e anonima.

La Fase 1 va costruita in modo che la Fase 2 sia un'estensione naturale, non una riscrittura.

*Sulle cinque lingue:* italiano, inglese, francese, spagnolo e arabo. L'arabo è incluso come obiettivo; se la resa vocale non fosse adeguata, resta comunque garantito il ripiego sul testo, senza compromettere il resto.

---

## 9. Qualità, test e sicurezza (priorità assoluta)

- **Test dal primo giorno (TDD).** Si scrivono prima i test, poi il codice.
- **Solo dati sintetici.** Mai dati reali di persone. Si usano personas sintetiche varie per età, lingua, competenze, esperienze e vicinanza al fine pena.
- **I test più importanti sono quelli sulla tenuta del sistema:**
  - il controllo dell'ambito regge (il sistema rifiuta tutto ciò che è fuori tema);
  - i rifiuti avvengono in modo controllato;
  - resistenza ai tentativi di manipolazione (prompt injection) e di estrazione di dati;
  - nessuna fuoriuscita di dati personali; filtraggio in uscita.
- **A seguire:** validatori dello schema del profilo, coerenza dell'estrazione, gestione delle incongruenze, correttezza del meccanismo di riepilogo e conferma.
- **Garanzie di sicurezza da rispettare** (il *come* è nel documento tecnico): pseudonimizzazione, separazione tra dati di profilo e log di conversazione, cifratura a riposo e in transito, accessi a privilegio minimo, log di audit immutabile, blindatura della postazione (kiosk), filtro dei dati personali in uscita.

La sicurezza e l'integrità del sistema, insieme alla copertura dei test, sono condizioni per considerare completa qualsiasi funzionalità.

---

## 10. Criteri di successo

Il prototipo è riuscito quando, **con dati sintetici e su hardware modesto**:

- i guardrail reggono a test avversari: il sistema resta nell'ambito e non perde dati;
- i profili risultano **solo lavorativi**, realistici, **confermati dalla persona** e con le incongruenze risolte in conversazione;
- il matching è **spiegabile** e propone i gap formativi;
- il carico di validazione **non ricade sugli operatori**;
- accessibilità e multilingua funzionano, con **degrado elegante** (voce → testo, modello grande → modello più leggero);
- **nessun dato esce** verso l'esterno;
- tutto è **riproducibile a costo zero** con componenti open source.

Il metro non è "il programma parte", ma "il sistema si comporta come promesso, soprattutto quando viene messo alla prova".

---

## 11. Lingua e convenzioni

- **Documenti di progetto in italiano.**
- **Codice in inglese** (identificatori e commenti).
- **Stringhe rivolte all'utente esternalizzate** e predisposte per la traduzione (i18n), coerentemente con la natura multilingua del sistema.

---

## 12. Documento tecnico collegato

Questo documento è autoconsistente: si comprende da solo.

Accanto ad esso, l'assistente di sviluppo crea e mantiene un **documento tecnico vivo** (nome indicativo: `STATO_TECNICO.md`) che contiene il **come**: lo stack open source scelto, i modelli selezionati con la loro motivazione, i comandi, il modo di eseguire i test, le decisioni operative. Questo documento **non fa parte del nucleo protetto** e può evolvere liberamente. È tenuto separato apposta, per lasciare il presente documento stabile e funzionale.

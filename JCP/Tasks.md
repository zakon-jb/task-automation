## Backlog

- [ ] (Artem/Mikhail) LV - what's the issue? To check with Artem/Mikhail 
- [ ] (Gleb) Customer migration checklist (with Gleb)
- [ ] (Gleb) Tech stream: Backstage for OpenAPI specs? Gleb will go to service owners (+ add to service readiness checklist) #monitoring
- [ ] (Gleb) Two-phase migration (+ testing procedure) #monitoring
	- Sergey Zhuravlev will discuss with Gleb
- [ ] (Pavel Nikitin) Tech: Thirdparty libs #monitoring
- [ ] (Maria) Duplicated channels for Seats and Billing
- [ ] (Olga + Dima) Orca Consumption API - after April 10
- [ ] Communication to 'lost' users - how/when/who?
- [ ] JCP - BAD corner cases for EAP Global
	- (Gleb) changing customer type: personal → organization
	- (Gleb) products without a license (e.g. Android Studio)
	- (Gleb) merging customers after migration
- [ ] (Gleb) New protocol of communication between AI tools <-> Pre-billing <-> BAD
- [ ] Tech stream: How to test multi-region? to discuss with Kirill Falk (Vlad Chentsov)
	- Add API Gateways to https://docs.google.com/spreadsheets/d/1Kur312UvSVoK5rzX1ZfsmFzyy5zQIAcFViD7_BfQTxI/edit?gid=0#gid=0
	- https://youtrack-staging.labs.intellij.net/issue/JCP-2626/Multi-Region-testing
- [ ] Issue tracking in Pre-billing (meet with Dima and Kirill)
- [ ] Migration of JB - plan
- [ ] List of endpoints for LLM by Junie (and ability to switch to v9) https://youtrack.jetbrains.com/issue/MTRH-2679/Please-provide-a-list-of-AI-Platform-endpoints-used-by-Junie #monitoring
- [ ] Dogfooding JB - team lead role? (Artem) #monitoring ⏫
- [ ] Can we freeze AI licenses after migration? (question to Sergey Coox) https://youtrack.jetbrains.com/issue/BAD-21711/Disable-AI-Pro-Ultimate-license #monitoring
- [ ] Banner for AIP/AIPU licenses on the web site #active
- [ ] Tech stream: Checklist for services -> hand over to On-Call: verify checklist (A.Sizov) #active 
- [ ] Tech stream: Kick-off for front-end monitoring: setup process for front-end alerts (Sizov + Ksenia + Akif) #active 
- [ ] Anti-fraud 2.0 estimates (Dmitry B) #active 
- [ ] Pre-prod: fix from Dmitry Borin needed (mentioned by Maksim Manuylov) -> required for updating AuthZ #active 
- [ ] Gleb: access to envs (staging / prod) #active 
- [ ] Dmitry Borin: we need a multi-reg for Pre-prod (maybe not from the beginning)
- [/] IDE features for JCP - versions (IDE, plugins) #active ⏫
- [/] Minutes EAP scope #active
- [ ] Retrospective Licensing and Billing team #active ⏫
- [/] Dogfooding QA board #active ⏫
- [ ] Licensing and Billing - new planning framework #active ⏫
- [ ] Thirdparty libraries - reopen: separate Air Cloud (ask PMs), frontend for Air Cloud, BAD, trigger for daily updates #active 
- [ ] Pre-prod working group + 1 hour meeting (Gleb + Kirill + A.Sizov + Pavel N.) #active 
- [ ] Dogfooding bugfix process - connect with Alexander Ivlev #active 
- [ ] Coordinate Wire #active 
- [/] EAP Global Scope #active 🔺
- [ ] What's wrong with issuing org service account tokens? #active 

## Archive

- [x] Open question: AIF or AIP allowance ✅ 2026-03-31
- [x] (LLM) Strange critical bug https://youtrack.jetbrains.com/issue/JBAIP-762/Unable-to-update-Grazie-Platform-in-monorepo-due-to-unresolved-transitive-dependency-tanvd.konfykonfy0.1.30 ✅ 2026-03-31
- [x] (Data Analysts) Check distribution https://youtrack.jetbrains.com/issue/JBAI-20223/Distribution-of-companies-by-the-number-of-license-periods #active ✅ 2026-04-01
- [x] (Gleb) Open question: Grazie lite - perpetual license ✅ 2026-04-01
	- https://youtrack.jetbrains.com/issue/JCP-2082/AI-Seats-migration-support-Grazie-product
- [x] Tech stream: Multi-region flags, discuss ETA https://youtrack.jetbrains.com/issue/JCP-2684/Configure-multi-region-AI-Platform-services-to-get-JCP-feature-flags #active ⏫ ✅ 2026-04-02
- [x] Do we need a dedicated feature flag for enabling paid features (question to Mikhail) #active ✅ 2026-04-07
- [x] Risk with context_principal (context - Sam) #active ⏫ ✅ 2026-04-07
- [x] AIF annual - 36 credits? (ask Mikhail) #active ✅ 2026-04-07
- [x] Unblock LLM with org service account support on Pre-billing #active ⏫ ✅ 2026-04-07
- [x] Validate solution: https://youtrack.jetbrains.com/issue/BAD-21509/Implement-recurring-credits-top-up-processing-integration-with-JCP #active 🔺 ✅ 2026-04-07
- [x] Minutes for Auto-refill #active 🔺 ✅ 2026-04-07
- [x] New meeting for auto refills #active ⏫ ✅ 2026-04-08
- [x] Create tasks for multi-regional deployment of AICS and Secret Service https://youtrack.jetbrains.com/articles/JCP-A-299/Setup-Multi-Regional-Deployment-Production #active ✅ 2026-04-08
- [x] Add meeting for Seats user story - Products (Artem, Viktor), Kirill, Maria Chuprasova, Chentsov? #active ✅ 2026-04-08
- [x] Pre-release checklist https://jetbrains.slack.com/archives/C0AQYAFCS9X/p1775641899131319 #active ⏫ ✅ 2026-04-10
- [x] Minutes e2e seats #active 🔺 ✅ 2026-04-11
- [x] Agree on due dates for Junie tasks (web search) #active ⏫ ✅ 2026-04-13
- [x] Cross-project "JCP Milestone" field #active ⏫ ✅ 2026-04-21
	- https://youtrack-staging.labs.intellij.net/issue/JT-95117/I-need-to-reuse-an-enum-custom-field-across-different-YouTrack-projects
- [x] Scope for EAP Global #active 🔺 ✅ 2026-04-21
	1. Paid seats, upgrade/downgrade (AI Gov + Pre-billing)
	2. Auto-refill credit subscriptions (AI Gov + Pre-billing + BAD)
	3. Postpaid (AI Gov + Pre-billing + BAD)
	4. Trials (IDEs + Pre-billing + AI Gov?)
	5. Orca consumption API (Orca + Pre-billing)
	6. Ledger
	7. Credit offers
	8. Refunds?
- [x] AIR task for switching to the new Tavily API #active ⏫ ✅ 2026-04-21
- [x] Paid seats - in scope DP or not? #active ⏫ ✅ 2026-04-16
- [x] Dogfooding wire - how technically can it work with our staging? #active 🔺 ✅ 2026-04-16
- [x] Annual $200 or $240 ($20 x 12) #active 🔺 ✅ 2026-04-16
- [x] Meeting Technical migration next week #active ⏫ ✅ 2026-04-21
- [x] Can Air team and Remote agents be enabled independently? #active 🔺 ✅ 2026-04-21
- [x] Create task for BAD: Linked accounts: If there is a linked account, it should be primary assignee (BAD) #active ⏫ ✅ 2026-04-21
- [x] (Mikhail) Finance issue #monitoring ⏫ ✅ 2026-04-24
- [x] Add AI Business license to the web site - need ticket! #active ⏫ ✅ 2026-04-24
- [x] Air login #active ✅ 2026-04-24
- [x] Task for Wire (Marcin): JCP login #active ✅ 2026-04-24
- [x] Minutes recurrent payments #active ✅ 2026-04-25
- [x] Read https://docs.google.com/document/d/1nkeqOMWptOPhILXFqN-H2tjfT4QhkDJPOl9GMOYcn6s/edit?tab=t.0 #active ✅ 2026-04-29

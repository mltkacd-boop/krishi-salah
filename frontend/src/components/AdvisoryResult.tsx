import { useState } from 'react'

import { useLanguage } from '../i18n/LanguageProvider'
import type { StringKey } from '../i18n/strings'
import type {
  AdvisoryCitation,
  AdvisoryResponse,
  RuleFinding,
  SafetyDisclosure,
} from '../types/api'
import { Card, Section } from './Card'
import { ConfidenceMeter } from './ConfidenceMeter'
import { DecisionBadge } from './DecisionBadge'
import { Icon } from './Icon'

const FIELD_LABEL: Record<string, StringKey> = {
  phi: 'field.phi',
  rei: 'field.rei',
  ppe: 'field.ppe',
  dosage: 'field.dosage',
  regulatory_approval: 'field.regulatory_approval',
  source_verification: 'field.source_verification',
}

const SEVERITY_STYLE: Record<string, string> = {
  block: 'bg-danger-100 text-danger-700',
  restrict_actionability: 'bg-gold-100 text-gold-800',
  warn: 'bg-ivory-200 text-ink-700',
}

/** Plain words for a rule's severity; the machine value stays in the trace. */
const SEVERITY_LABEL: Record<string, StringKey> = {
  block: 'safety.severity.block',
  restrict_actionability: 'safety.severity.restrict',
  warn: 'safety.severity.warn',
}

function disclosureKey(item: SafetyDisclosure): string {
  return `${item.field}|${item.status}|${item.value ?? ''}|${item.note ?? ''}`
}

/** PHI / REI / PPE, one row each, with the source's own status. */
function SafetyPanel({ disclosures }: { disclosures: SafetyDisclosure[] }) {
  const { t, lang } = useLanguage()
  const unique = disclosures.filter(
    (item, index, all) => all.findIndex((other) => disclosureKey(other) === disclosureKey(item)) === index,
  )

  if (unique.length === 0) {
    return (
      <p className="text-sm text-ink-500">
        {lang === 'hi'
          ? 'इस उत्तर में कोई सुरक्षा विवरण नहीं है।'
          : 'No safety disclosure was returned for this answer.'}
      </p>
    )
  }

  return (
    <div className="divide-y divide-ivory-200">
      {unique.map((item) => {
        const published = item.status === 'PUBLISHED'
        return (
          <div
            key={disclosureKey(item)}
            className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:gap-4"
          >
            <div className="flex w-56 flex-shrink-0 items-center gap-2">
              <span className="text-sm font-medium text-ink-800">
                {t(FIELD_LABEL[item.field] ?? 'field.phi')}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={
                    'rounded-full px-2 py-0.5 text-2xs font-semibold uppercase tracking-[0.1em] ' +
                    (published ? 'bg-forest-100 text-forest-800' : 'bg-gold-100 text-gold-800')
                  }
                >
                  {published ? t('result.published') : t('result.notPublished')}
                </span>
                {published && item.value && (
                  <span className="text-sm text-ink-800">{item.value}</span>
                )}
              </div>
              {!published && item.note && (
                <p className="mt-1 text-xs leading-5 text-ink-500">
                  <span className="font-medium text-ink-700">{t('result.note')}: </span>
                  {item.note}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** A rule's message in plain words. Rule ids live in the technical section. */
function RuleFindings({ findings }: { findings: RuleFinding[] }) {
  const { t, lang } = useLanguage()
  if (findings.length === 0) {
    return (
      <p className="text-sm text-ink-500">
        {lang === 'hi'
          ? 'कोई नियम नहीं चला — निर्णय अनुरोध से पहले ही लौटा दिया गया।'
          : 'No rule ran before this decision was returned.'}
      </p>
    )
  }
  return (
    <ul className="space-y-3">
      {findings.map((finding, index) => (
        <li
          key={`${finding.code}-${index}`}
          /* A grid, not a flex row: a nowrap chip in a flex row can be squeezed
             under its own content and end up underneath the sentence. */
          className="grid gap-1 sm:grid-cols-[10.5rem_1fr] sm:items-start sm:gap-3"
        >
          <span
            className={
              'mt-0.5 h-fit w-fit whitespace-nowrap rounded px-1.5 py-0.5 text-2xs font-semibold leading-4 ' +
              (SEVERITY_STYLE[finding.severity] ?? 'bg-ivory-200 text-ink-700')
            }
          >
            {SEVERITY_LABEL[finding.severity] ? t(SEVERITY_LABEL[finding.severity]) : finding.severity}
          </span>
          <p className="min-w-0 text-sm leading-6 text-ink-800">{finding.message}</p>
        </li>
      ))}
    </ul>
  )
}

/** A source a farmer can open: name, authority, link, date. No hashes. */
function CitationCard({ citation }: { citation: AdvisoryCitation }) {
  const { t } = useLanguage()
  return (
    <li className="border-b border-ivory-200 py-3 first:pt-0 last:border-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <a
          href={citation.url}
          target="_blank"
          rel="noreferrer noopener"
          className="group inline-flex items-start gap-1.5 text-sm font-semibold text-forest-800 hover:text-forest-600"
        >
          {citation.title}
          <Icon name="external" className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 opacity-60 group-hover:opacity-100" />
        </a>
        <span className="rounded-full bg-ivory-100 px-2 py-0.5 text-2xs font-medium text-ink-700">
          {citation.reliability_tier.split('_').join(' ')}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-500">
        {citation.authority} · {t('result.retrieved')} {citation.retrieved_date}
      </p>
    </li>
  )
}

function TechRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-3 py-0.5">
      <dt className="min-w-[7.5rem] text-ink-500">{label}</dt>
      <dd className="min-w-0 break-all font-mono text-2xs text-ink-700">{value}</dd>
    </div>
  )
}

function TechBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="label-caps mb-1.5">{title}</p>
      <dl className="space-y-0.5">{children}</dl>
    </div>
  )
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-md bg-ivory-100 p-2 font-mono text-[10px] leading-4 text-ink-700">
      {JSON.stringify(value, null, 1)}
    </pre>
  )
}

/**
 * Everything a farmer must not have to read: decision codes, rule identifiers,
 * retrieval scores, record ids and provenance hashes. Collapsed, labelled as an
 * evaluation aid, and never the only place a safety fact appears.
 */
function TechnicalDetails({ response }: { response: AdvisoryResponse }) {
  const { t } = useLanguage()
  const [open, setOpen] = useState(false)
  const gateDetail = response.rule_trace?.gate_detail

  return (
    <div>
      {/* A controlled disclosure rather than <details>: the machine-readable
          payload is not mounted at all until it is asked for, so it cannot be
          reached by a screen reader or a text search while collapsed. */}
      <button
        type="button"
        aria-expanded={open}
        aria-controls="technical-details"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-medium text-ink-700 hover:text-ink-900 sm:px-6"
      >
        {t('result.technical')}
        <Icon
          name="chevron-down"
          className={
            'h-4 w-4 text-ink-400 transition-transform ' + (open ? 'rotate-180' : '')
          }
        />
      </button>
      <div
        id="technical-details"
        hidden={!open}
        className="space-y-4 border-t border-ivory-200 px-5 py-4 text-xs text-ink-600 sm:px-6"
      >
        {open && (
          <>
            <p className="max-w-2xl text-2xs leading-5 text-ink-500">{t('result.technicalNote')}</p>

        <TechBlock title={t('result.techDecision')}>
          <TechRow label="decision" value={response.decision ?? 'null'} />
          <TechRow label="outcome" value={response.outcome} />
          <TechRow label="advisory_status" value={response.advisory_status ?? 'null'} />
          <TechRow label="answer_scope" value={response.answer_scope} />
          <TechRow label="generation_mode" value={response.generation_mode} />
          {gateDetail !== undefined && (
            <TechRow label="gate_detail" value={String(gateDetail)} />
          )}
        </TechBlock>

        <TechBlock title={t('result.techConfidence')}>
          <TechRow label="confidence" value={response.confidence.toFixed(4)} />
          <TechRow label="confidence_label" value={response.confidence_label} />
        </TechBlock>
        <Json value={response.confidence_components} />

        {response.rule_findings.length > 0 && (
          <div>
            <p className="label-caps mb-1.5">{t('result.techRules')}</p>
            <div className="overflow-x-auto rounded-md border border-ivory-200">
              <table className="w-full min-w-[520px] text-left text-2xs">
                <thead className="bg-ivory-50 text-ink-500">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">rule_id</th>
                    <th className="px-3 py-1.5 font-medium">code</th>
                    <th className="px-3 py-1.5 font-medium">severity</th>
                    <th className="px-3 py-1.5 font-medium">action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ivory-200 font-mono">
                  {response.rule_findings.map((finding, index) => (
                    <tr key={`${finding.rule_id}-${index}`}>
                      <td className="px-3 py-1.5 text-ink-700">{finding.rule_id}</td>
                      <td className="px-3 py-1.5 text-ink-700">{finding.code}</td>
                      <td className="px-3 py-1.5 text-ink-700">{finding.severity}</td>
                      <td className="px-3 py-1.5 text-ink-700">{finding.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {response.evidence.length > 0 && (
          <div>
            <p className="label-caps mb-1.5">{t('result.techPassages')}</p>
            <div className="overflow-x-auto rounded-md border border-ivory-200">
              <table className="w-full min-w-[520px] text-left text-2xs">
                <thead className="bg-ivory-50 text-ink-500">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">chunk</th>
                    <th className="px-3 py-1.5 font-medium">type</th>
                    <th className="px-3 py-1.5 font-medium">record</th>
                    <th className="px-3 py-1.5 text-right font-medium">{t('result.score')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ivory-200 font-mono">
                  {response.evidence.map((item) => (
                    <tr key={item.chunk_ref}>
                      <td className="px-3 py-1.5 text-ink-700">{item.chunk_ref}</td>
                      <td className="px-3 py-1.5 text-ink-700">{item.chunk_type}</td>
                      <td className="px-3 py-1.5 text-ink-700">{item.approved_use_id ?? '—'}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums text-ink-700">
                        {item.score.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {response.citations.length > 0 && (
          <div>
            <p className="label-caps mb-1.5">{t('result.techCitations')}</p>
            <ul className="space-y-2">
              {response.citations.map((citation) => (
                <li key={citation.source_id} className="rounded-md bg-ivory-50 px-3 py-2">
                  <p className="font-mono text-2xs text-ink-700">{citation.source_id}</p>
                  <TechRow label="verification" value={citation.verification_status} />
                  <TechRow label="sha256" value={citation.provenance_sha256 ?? '—'} />
                  <TechRow label="records" value={citation.record_ids.join(', ') || '—'} />
                  <TechRow label="chunks" value={citation.chunk_refs.length} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {Object.keys(response.classification ?? {}).length > 0 && (
          <div>
            <p className="label-caps mb-1.5">{t('result.techClassification')}</p>
            <Json value={response.classification} />
          </div>
        )}

        <TechBlock title={t('result.techModel')}>
          {Object.entries(response.model_versions).map(([key, value]) => (
            <TechRow key={key} label={key} value={value} />
          ))}
          <TechRow label={t('result.usagePolicy')} value={JSON.stringify(response.usage_policy)} />
        </TechBlock>
          </>
        )}
      </div>
    </div>
  )
}

/** Outcome-specific guidance. Never a pesticide instruction. */
function nextStepKeys(outcome: string, answered: boolean, actionable: boolean): StringKey[] {
  switch (outcome) {
    case 'needs_clarification':
      return ['result.next.clarify']
    case 'out_of_scope':
      return ['result.next.unsupported', 'result.next.escalate']
    case 'unsupported_crop':
      return ['result.next.unsupported', 'result.next.escalate']
    case 'safety_value_not_published':
    case 'safety_contradiction':
      return ['result.next.refusal', 'result.next.registry']
    case 'no_regulatory_verification':
      return ['result.next.registry']
    default:
      // An answered question is only a reading suggestion unless the backend
      // marked the record actionable; anything else says so before it says
      // anything else.
      if (!answered) return ['result.next.escalate']
      return actionable
        ? ['result.next.registry']
        : ['result.next.educational', 'result.next.registry']
  }
}

export function AdvisoryResult({ response }: { response: AdvisoryResponse }) {
  const { t } = useLanguage()
  const answered = response.outcome === 'answered'
  const missing = response.missing_information ?? []

  const nextKeys = nextStepKeys(
    response.outcome,
    answered,
    response.advisory_status === 'ACTIONABLE_WITH_EVIDENCE',
  )

  return (
    <div className="space-y-4" data-testid="advisory-result">
      {/* B. Decision status — first, because a refusal must not be mistaken for
             an answer while the reader is still scrolling to the text. */}
      <DecisionBadge
        decision={response.decision}
        outcome={response.outcome}
        scope={response.answer_scope}
      />

      {/* A. Answer summary */}
      <Card>
        <div className="border-b border-ivory-200 px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="label-caps">{answered ? t('result.answer') : t('result.response')}</p>
              <p className="mt-1 max-w-2xl text-[15px] font-medium leading-6 text-ink-900">
                {response.query}
              </p>
            </div>
            <div className="w-full max-w-[15rem] sm:w-56">
              <ConfidenceMeter label={response.confidence_label} />
            </div>
          </div>
        </div>

        <div className="px-5 py-5 sm:px-6">
          {answered && response.answer ? (
            <>
              <div className="prose-answer">
                {response.answer.split('\n\n').map((paragraph, index) => (
                  <p key={index}>{paragraph}</p>
                ))}
              </div>

              {response.sections.length > 0 && (
                <dl className="mt-6 space-y-5 border-t border-ivory-200 pt-5">
                  {response.sections.map((section, index) => (
                    <div key={`${section.heading ?? 'section'}-${index}`}>
                      <dt className="text-sm font-semibold text-ink-900">{section.heading}</dt>
                      <dd className="mt-1.5">
                        <ul className="space-y-1.5">
                          {(section.items ?? []).map((item, itemIndex) => (
                            <li
                              key={itemIndex}
                              className="flex gap-2.5 text-sm leading-6 text-ink-700"
                            >
                              <span className="mt-2.5 h-1 w-1 flex-shrink-0 rounded-full bg-forest-500" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </>
          ) : (
            <div>
              <p className="text-sm leading-7 text-ink-800 sm:text-[15px]">
                {response.message ?? t('result.gateWhy')}
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-ivory-200 px-5 py-3 text-2xs text-ink-500 sm:px-6">
          <span>
            {t('result.answerLanguage')}: {response.answer_language === 'hi' ? 'हिंदी' : 'English'}
          </span>
          {answered && (
            <span>
              {response.answer_scope === 'crop' ? t('result.scope.crop') : t('result.scope.record')}
            </span>
          )}
        </div>
      </Card>

      {/* D (part 1). Missing safety information — never collapsed, never hidden. */}
      {missing.length > 0 && (
        <Card className="border-gold-300 bg-gold-50 p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gold-100 text-gold-800">
              <Icon name="alert" className="h-5 w-5" />
            </span>
            <div>
              <h2 className="font-display text-[15px] font-semibold text-gold-900">
                {t('result.missing')}
              </h2>
              <div className="mt-2 flex flex-wrap gap-2">
                {missing.map((field) => (
                  <span
                    key={field}
                    className="rounded-full border border-gold-300 bg-white px-2.5 py-1 text-xs font-medium text-gold-900"
                  >
                    {FIELD_LABEL[field] ? t(FIELD_LABEL[field]) : field}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-xs leading-5 text-gold-800">{t('result.missingBody')}</p>
            </div>
          </div>
        </Card>
      )}

      {/* C. Evidence and sources. An empty source card on a refusal says nothing
             the decision above has not already said, so it is only rendered when
             there is something to cite (or when the answer itself is supported). */}
      {(answered || response.citations.length > 0) && (
        <Card>
          <Section
            title={t('result.citations')}
            icon={<Icon name="book" className="h-4 w-4 text-ink-400" />}
            aside={
              <span className="text-2xs text-ink-500">
                {response.citations.length} {t('result.sourceCount')}
              </span>
            }
          >
            {response.citations.length === 0 ? (
              <p className="text-sm text-ink-500">{t('result.noCitations')}</p>
            ) : (
              <ul className="divide-y divide-ivory-200">
                {response.citations.map((citation) => (
                  <CitationCard key={citation.source_id} citation={citation} />
                ))}
              </ul>
            )}
          </Section>
        </Card>
      )}

      {/* D (part 2). Safety data for the matched record */}
      {answered && (
        <Card>
          <Section
            title={t('result.safety')}
            icon={<Icon name="shield" className="h-4 w-4 text-ink-400" />}
            aside={
              <span
                className={
                  'rounded-full px-2 py-0.5 text-2xs font-medium ' +
                  (response.advisory_status === 'ACTIONABLE_WITH_EVIDENCE'
                    ? 'bg-forest-100 text-forest-800'
                    : 'bg-gold-100 text-gold-800')
                }
              >
                {response.advisory_status === 'ACTIONABLE_WITH_EVIDENCE'
                  ? t('decision.ACTIONABLE_RECOMMENDATION')
                  : t('kb.educational')}
              </span>
            }
          >
            <SafetyPanel disclosures={response.safety_disclosures} />
            <p className="mt-4 border-t border-ivory-200 pt-3 text-2xs leading-5 text-ink-500">
              {t('result.policy')}
            </p>
          </Section>
        </Card>
      )}

      {/* E. Next steps */}
      <Card className="border-l-4 border-l-forest-700">
        <Section
          title={t('result.next.title')}
          icon={<Icon name="arrow-right" className="h-4 w-4 text-forest-700" />}
        >
          <ul className="space-y-2.5">
            {nextKeys.map((key) => (
              <li key={key} className="flex gap-2.5 text-sm leading-6 text-ink-800">
                <span className="mt-2.5 h-1 w-1 flex-shrink-0 rounded-full bg-forest-600" />
                <span>{t(key)}</span>
              </li>
            ))}
          </ul>
        </Section>
      </Card>

      {/* Why — the rule that produced the decision, in plain words */}
      <Card>
        <Section
          title={t('result.why')}
          icon={<Icon name="shield" className="h-4 w-4 text-ink-400" />}
        >
          {response.rule_findings.length > 0 ? (
            <RuleFindings findings={response.rule_findings} />
          ) : (
            <p className="text-sm leading-6 text-ink-800">{t('result.gateWhy')}</p>
          )}
        </Section>
      </Card>

      {/* Evaluation detail: machine-readable only, collapsed by default. */}
      <Card className="bg-ivory-50">
        <TechnicalDetails response={response} />
      </Card>
    </div>
  )
}


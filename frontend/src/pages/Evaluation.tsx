import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Card, Section } from '../components/Card'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { useLanguage } from '../i18n/LanguageProvider'
import { advisoryService } from '../services/advisoryService'
import { classificationService } from '../services/classificationService'
import { knowledgeBaseService } from '../services/knowledgeBaseService'
import type {
  KnowledgeBaseStatusResponse,
  ModelInfoResponse,
  RagStatusResponse,
  RulesStatusResponse,
} from '../types/api'

/**
 * Project-evaluation view.
 *
 * Everything the product deliberately hides from a farmer — rule identifiers,
 * thresholds, retrieval scores, model versions, storage backends — lives here,
 * behind a route that is linked from the footer only. It reads the same public
 * GET endpoints the rest of the app uses; there are no credentials, keys or
 * connection strings on this page because the backend never returns any.
 *
 * The project title is the only submission metadata kept: it names the system
 * under test. Student name, registration number, section, course and project
 * type are deliberately absent — they identify the submitter, not the build.
 */
/**
 * Diagnostics are read straight off the API, and some of them are nested
 * (the classifier thresholds are keyed by target). A raw object cannot be a
 * React child, so anything non-primitive is flattened to `key value · key
 * value` here rather than being rendered as `[object Object]`.
 */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') {
    if (Array.isArray(value)) return value.map(formatValue).join(', ')
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${key} ${formatValue(nested)}`)
      .join(' · ')
  }
  return String(value)
}

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="grid gap-x-4 border-b border-ivory-200 py-1.5 text-xs last:border-b-0 sm:grid-cols-[minmax(7rem,11rem)_1fr]">
      <dt className="font-mono text-2xs leading-5 text-ink-500">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-ink-800">{formatValue(value)}</dd>
    </div>
  )
}

function Json({ value }: { value: unknown }) {
  return (
    <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-md bg-ivory-50 p-2.5 font-mono text-[10px] leading-4 text-ink-600">
      {JSON.stringify(value, null, 1)}
    </pre>
  )
}

interface State {
  rag: RagStatusResponse | null
  rules: RulesStatusResponse | null
  model: ModelInfoResponse | null
  kb: KnowledgeBaseStatusResponse | null
  failed: string[]
  loading: boolean
}

export function Evaluation() {
  const { t } = useLanguage()
  const [state, setState] = useState<State>({
    rag: null,
    rules: null,
    model: null,
    kb: null,
    failed: [],
    loading: true,
  })

  useEffect(() => {
    let cancelled = false
    const calls: Array<[keyof Omit<State, 'failed' | 'loading'>, Promise<unknown>]> = [
      ['rag', advisoryService.status()],
      ['rules', advisoryService.rulesStatus()],
      ['model', classificationService.modelInfo()],
      ['kb', knowledgeBaseService.status()],
    ]

    Promise.allSettled(calls.map(([, promise]) => promise)).then((settled) => {
      if (cancelled) return
      const next: State = { rag: null, rules: null, model: null, kb: null, failed: [], loading: false }
      settled.forEach((result, index) => {
        const key = calls[index][0]
        if (result.status === 'fulfilled') {
          // Each call resolves to its own shape; the key names it.
          ;(next as unknown as Record<string, unknown>)[key] = result.value
        } else {
          next.failed.push(calls[index][0])
        }
      })
      setState(next)
    })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader title={t('eval.title')} description={t('eval.subtitle')} />

      <div className="flex items-start gap-3 rounded-card border border-ivory-300 bg-ivory-50 px-4 py-3.5 sm:px-5">
        <Icon name="info" className="mt-0.5 h-4 w-4 flex-shrink-0 text-ink-500" />
        <p className="text-xs leading-5 text-ink-600">{t('eval.note')}</p>
      </div>

      {state.loading && (
        <Card className="p-5">
          <span role="status" className="text-sm text-ink-500">
            {t('eval.loading')}
          </span>
        </Card>
      )}

      {!state.loading && state.failed.length > 0 && (
        <Card className="border-danger-200 bg-danger-50 p-4 text-xs text-danger-700">
          {t('eval.error')}: {state.failed.join(', ')}
        </Card>
      )}

      {state.rag && (
        <Card>
          <Section
            title={t('eval.retrieval')}
            icon={<Icon name="database" className="h-4 w-4 text-ink-400" />}
          >
            <dl>
              <Row label="vector_backend" value={state.rag.vector_backend} />
              <Row label="embedding_model" value={state.rag.embedding_model} />
              <Row label="indexed_chunks" value={state.rag.indexed_chunks} />
              <Row label="repository_backend" value={state.rag.repository_backend ?? t('eval.unavailable')} />
              <Row label="classifier_version" value={state.rag.classifier_version} />
              <Row label="generation_mode" value={state.rag.generation_mode} />
            </dl>
            <p className="label-caps mt-4 mb-1.5">thresholds</p>
            <dl>
              {Object.entries(state.rag.thresholds).map(([key, value]) => (
                <Row key={key} label={key} value={value} />
              ))}
            </dl>
          </Section>
        </Card>
      )}

      {state.rules && (
        <Card>
          <Section
            title={t('eval.rules')}
            icon={<Icon name="shield" className="h-4 w-4 text-ink-400" />}
            aside={
              <span className="text-2xs text-ink-500">
                {state.rules.engine} · {t('safety.involvement')}: {state.rules.generation_involvement}
              </span>
            }
          >
            <div className="overflow-x-auto rounded-md border border-ivory-200">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead className="bg-ivory-50 text-2xs text-ink-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">rule_id</th>
                    <th className="px-3 py-2 font-medium">severity</th>
                    <th className="px-3 py-2 font-medium">action</th>
                    <th className="px-3 py-2 font-medium">trigger</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ivory-200">
                  {state.rules.rules.map((rule) => (
                    <tr key={rule.rule_id}>
                      <td className="px-3 py-2 align-top font-mono text-2xs text-ink-800">
                        {rule.rule_id}
                      </td>
                      <td className="px-3 py-2 align-top">{rule.severity}</td>
                      <td className="px-3 py-2 align-top font-mono text-2xs">{rule.action}</td>
                      <td className="px-3 py-2 align-top leading-5 text-ink-600">{rule.trigger}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div>
                <p className="label-caps mb-1.5">block_precedence</p>
                <ol className="space-y-1">
                  {state.rules.block_precedence.map((ruleId, index) => (
                    <li key={ruleId} className="flex gap-2 text-xs text-ink-700">
                      <span className="w-4 text-right tabular-nums text-ink-400">{index + 1}.</span>
                      <code className="font-mono text-2xs">{ruleId}</code>
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <p className="label-caps mb-1.5">thresholds</p>
                <dl>
                  {Object.entries(state.rules.thresholds).map(([key, value]) => (
                    <Row key={key} label={key} value={value} />
                  ))}
                </dl>
              </div>
            </div>

            <div className="mt-4 border-t border-ivory-200 pt-3">
              <dl>
                <Row label="records" value={state.rules.knowledge_base.records} />
                <Row
                  label="actionable_with_evidence"
                  value={state.rules.knowledge_base.actionable_with_evidence}
                />
                <Row label="educational_only" value={state.rules.knowledge_base.educational_only} />
              </dl>
              <p className="mt-2 text-xs leading-5 text-ink-600">
                <span className="text-ink-500">{t('eval.reason')}: </span>
                {state.rules.knowledge_base.reason}
              </p>
            </div>
          </Section>
        </Card>
      )}

      {state.model && (
        <Card>
          <Section
            title={t('eval.classifier')}
            icon={<Icon name="spark" className="h-4 w-4 text-ink-400" />}
            aside={<span className="font-mono text-2xs text-ink-500">{state.model.model_version}</span>}
          >
            <dl>
              <Row label="classifier_type" value={state.model.classifier_type} />
              <Row label="trained_at" value={state.model.trained_at ?? t('eval.unavailable')} />
            </dl>
            <p className="label-caps mt-4 mb-1.5">targets</p>
            <dl>
              {Object.entries(state.model.targets).map(([head, labels]) => (
                <Row key={head} label={head} value={labels.join(', ')} />
              ))}
            </dl>
            <p className="label-caps mt-4 mb-1.5">thresholds</p>
            <Json value={state.model.thresholds} />
            <p className="label-caps mt-4 mb-1.5">training_metadata</p>
            <Json value={state.model.training_metadata} />
            <p className="mt-2 text-xs leading-5 text-ink-600">{state.model.note}</p>
          </Section>
        </Card>
      )}

      {state.kb && (
        <Card>
          <Section
            title={t('eval.kb')}
            icon={<Icon name="database" className="h-4 w-4 text-ink-400" />}
          >
            <dl>
              <Row label="repository_backend" value={state.kb.repository_backend ?? t('eval.unavailable')} />
              <Row label="repository_configured" value={state.kb.repository_configured ?? t('eval.unavailable')} />
              <Row label="repository_class" value={state.kb.repository_class ?? t('eval.unavailable')} />
              <Row label="fallback_reason" value={state.kb.repository_fallback_reason ?? '—'} />
              <Row label="env_var" value={state.kb.kb_repository_env_var} />
            </dl>
            <p className="label-caps mt-4 mb-1.5">vector_store</p>
            <Json value={state.kb.vector_store} />
            {state.kb.records && (
              <>
                <p className="label-caps mt-4 mb-1.5">records</p>
                <Json value={state.kb.records} />
              </>
            )}
          </Section>
        </Card>
      )}

      <Card>
        <Section
          title={t('eval.academic')}
          icon={<Icon name="document" className="h-4 w-4 text-ink-400" />}
        >
          <dl>
            {/* The technical project title only. Submission metadata — student,
                section, course, project type — belongs to the coursework, not to
                the system under evaluation, and is deliberately absent. */}
            <Row
              label="project_title"
              value="Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support"
            />
          </dl>
          <p className="mt-3 text-xs leading-5 text-ink-500">
            <Link to="/project-info" className="hover:text-forest-800 hover:underline">
              {t('about.title')}
            </Link>
          </p>
        </Section>
      </Card>
    </div>
  )
}

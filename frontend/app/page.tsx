'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BriefcaseBusiness,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Command,
  Download,
  Gauge,
  LayoutDashboard,
  Menu,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
  X,
  Zap,
} from 'lucide-react';

const API = '';
const PAGE_SIZE = 25;

type Dashboard = {
  employees: number;
  projects: number;
  active_projects: number;
  skills: number;
  demand_records: number;
  skill_gap_records: number;
  average_utilization: number;
  overallocated_periods: number;
  active_exceptions: number;
};

type Row = Record<string, string | number | boolean | null | undefined>;
const navigation = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'People', icon: Users },
  { name: 'Projects', icon: BriefcaseBusiness },
  { name: 'Skill gaps', icon: Activity },
  { name: 'Exceptions', icon: ShieldAlert },
  { name: 'Data & exports', icon: ArrowDownToLine },
] as const;

const exportNames = [
  'employees',
  'roles',
  'skills',
  'employee_skills',
  'projects',
  'demand',
  'allocations',
  'availability',
  'training',
  'gaps',
  'ground_truth',
  'audit',
];

const canonicalExceptionIds = new Set(['GT-001', 'GT-002', 'GT-003', 'GT-004']);

function display(value: Row[string]) {
  return value === null || value === undefined || value === '' ? '—' : String(value);
}

async function getJson<T,>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export default function Home() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [people, setPeople] = useState<Row[]>([]);
  const [projects, setProjects] = useState<Row[]>([]);
  const [gaps, setGaps] = useState<Row[]>([]);
  const [exceptions, setExceptions] = useState<Row[]>([]);
  const [forecasts, setForecasts] = useState<Row[]>([]);
  const [activePage, setActivePage] = useState<string>('Overview');
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [analysisReady, setAnalysisReady] = useState(false);
  const dashboardLoaded = useRef(false);

  const loadData = useCallback(async (pageOffset = offset, page = activePage, refreshDashboard = false) => {
    setBusy(true);
    setError('');
    try {
      const requests: Promise<void>[] = [];
      if (
        ['Overview', 'People', 'Projects', 'Skill gaps'].includes(page)
        && (page === 'Overview' || refreshDashboard || !dashboardLoaded.current)
      ) {
        requests.push(getJson<Dashboard>(`${API}/api/dashboard`).then((data) => {
          dashboardLoaded.current = true;
          setDashboard(data);
          setAnalysisReady(data.skill_gap_records > 0);
        }));
      }
      if (page === 'Overview') {
        requests.push(
          getJson<Row[]>(`${API}/api/gaps?limit=8`).then(setGaps),
          getJson<Row[]>(`${API}/api/exceptions`).then(setExceptions),
          getJson<{ forecasts: Row[] }>(`${API}/api/forecast`).then((data) => setForecasts(data.forecasts ?? [])),
        );
      } else if (page === 'People') {
        requests.push(
          getJson<Row[]>(`${API}/api/employees?limit=${PAGE_SIZE}&offset=${pageOffset}`).then(setPeople),
        );
      } else if (page === 'Projects') {
        requests.push(
          getJson<Row[]>(`${API}/api/projects?limit=${PAGE_SIZE}&offset=${pageOffset}`).then(setProjects),
        );
      } else if (page === 'Skill gaps') {
        requests.push(
          getJson<Row[]>(`${API}/api/gaps?limit=${PAGE_SIZE}&offset=${pageOffset}`).then(setGaps),
        );
      } else if (page === 'Exceptions') {
        requests.push(getJson<Row[]>(`${API}/api/exceptions`).then(setExceptions));
      }
      await Promise.all(requests);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to connect to the workforce API.');
    } finally {
      setBusy(false);
    }
  }, [activePage, offset]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredPeople = useMemo(
    () => people.filter((person) =>
      `${person.id} ${person.name} ${person.department} ${person.employment_type}`
        .toLowerCase()
        .includes(search.toLowerCase())),
    [people, search],
  );
  const filteredProjects = useMemo(
    () => projects.filter((project) =>
      `${project.id} ${project.name} ${project.department} ${project.status}`
        .toLowerCase()
        .includes(search.toLowerCase())),
    [projects, search],
  );

  async function runAnalysis() {
    setBusy(true);
    setError('');
    try {
      await getJson<{ gaps: number; detected_exceptions: number }>(`${API}/api/analysis/run`, {
        method: 'POST',
      });
      setAnalysisReady(true);
      await loadData(offset, activePage, true);
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : 'Analysis could not be completed.');
    } finally {
      setBusy(false);
    }
  }

  function navigateTo(page: string) {
    setActivePage(page);
    setSearch('');
    setOffset(0);
    setMobileNavOpen(false);
  }

  function changePage(nextOffset: number) {
    setOffset(nextOffset);
  }

  const pageTitle = activePage === 'Overview' ? 'Your workforce, in focus.' : activePage;
  const subtitle = activePage === 'Overview'
    ? 'A clear view of your people, project demand and the decisions ahead.'
    : activePage === 'Exceptions'
      ? 'Understand each planning issue, why it matters, and what to review.'
    : 'Find the information you need and take the next step with confidence.';

  return (
    <main className="app-shell">
      {mobileNavOpen && <button aria-label="Close navigation" className="mobile-backdrop" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); navigateTo('Overview'); }}>
          <span className="brand-symbol"><Command size={19} strokeWidth={2.2} /></span>
          <span className="brand-word">people<span>flow</span></span>
        </a>

        <div className="workspace-picker">
          <span className="workspace-avatar">W</span>
          <span className="workspace-copy"><strong>Workforce plan</strong><small>Planning workspace</small></span>
          <span className="workspace-caret">⌄</span>
        </div>

        <p className="nav-caption">YOUR WORKSPACE</p>
        <nav className="main-nav" aria-label="Main navigation">
          {navigation.map(({ name, icon: Icon }) => (
            <button
              className={`nav-link ${activePage === name ? 'nav-link-active' : ''}`}
              key={name}
              onClick={() => navigateTo(name)}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{name}</span>
              {activePage === name && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <span className="help-icon"><CircleHelp size={17} /></span>
            <div><strong>Need a hand?</strong><small>Your quick guide is ready.</small></div>
            <ArrowUpRight size={15} />
          </div>
          <div className="profile-card">
            <span className="profile-avatar">WP</span>
            <span className="profile-copy"><strong>Planning team</strong><small>Workspace admin</small></span>
            <span className="online-indicator" title="Connected" />
          </div>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)}><Menu size={20} /></button>
            <span className="breadcrumb">Workspace <span>/</span> <strong>{activePage}</strong></span>
          </div>
          <div className="topbar-right">
            <span className="data-status"><i /> {dashboard ? 'Your data is up to date' : 'Connecting to your data'}</span>
            <button className={`refresh-button ${busy ? 'is-spinning' : ''}`} onClick={() => void loadData(offset, activePage, true)} aria-label="Refresh dashboard" disabled={busy}>
              <RefreshCw size={17} />
            </button>
            <span className="top-avatar">WP</span>
          </div>
        </header>

        <div className="page-content">
          <div className="page-intro">
            <div>
              <p className="eyebrow"><span className="eyebrow-mark" /> PEOPLE & PROJECT INTELLIGENCE</p>
              <h1>{pageTitle}</h1>
              <p className="page-subtitle">{subtitle}</p>
            </div>
            <button className="button button-primary" onClick={runAnalysis} disabled={busy}>
              <Zap size={16} fill="currentColor" />
              {busy ? 'Updating…' : 'Refresh planning'}
            </button>
          </div>

          {error && (
            <div className="feedback feedback-error" role="alert">
              <ShieldAlert size={18} />
              <div><strong>We couldn’t load your planning data.</strong><span>{error}. Check that the backend is running, then try again.</span></div>
              <button onClick={() => void loadData(offset, activePage, true)} aria-label="Retry"><RefreshCw size={16} /></button>
            </div>
          )}
          {activePage === 'Overview' && (
            <Overview
              dashboard={dashboard}
              gaps={gaps}
              exceptions={exceptions}
              forecasts={forecasts}
              analysisReady={analysisReady}
              onNavigate={navigateTo}
            />
          )}
          {activePage === 'People' && (
            <DirectoryPage
              title="People directory"
              description="Browse your workforce and understand team capacity."
              search={search}
              setSearch={setSearch}
              rows={filteredPeople}
              columns={['id', 'name', 'department', 'employment_type', 'weekly_hours', 'status']}
              total={dashboard?.employees ?? 0}
              offset={offset}
              pageSize={PAGE_SIZE}
              changePage={changePage}
              placeholder="Search people on this page"
            />
          )}
          {activePage === 'Projects' && (
            <DirectoryPage
              title="Project portfolio"
              description="See the work that shapes your workforce plan."
              search={search}
              setSearch={setSearch}
              rows={filteredProjects}
              columns={['id', 'name', 'department', 'status', 'priority', 'start_date']}
              total={dashboard?.projects ?? 0}
              offset={offset}
              pageSize={PAGE_SIZE}
              changePage={changePage}
              placeholder="Search projects on this page"
            />
          )}
          {activePage === 'Skill gaps' && (
            <DirectoryPage
              title="Skill gap register"
              description="Demand lines where qualified capacity may need attention."
              rows={gaps}
              columns={['demand_id', 'required_fte', 'available_fte', 'gap_fte', 'status']}
              total={dashboard?.skill_gap_records ?? 0}
              offset={offset}
              pageSize={PAGE_SIZE}
              changePage={changePage}
              emptyMessage={analysisReady ? 'No uncovered demand lines were returned.' : 'Refresh planning to calculate skill gaps.'}
            />
          )}
          {activePage === 'Exceptions' && <ExceptionsPage rows={exceptions} />}
          {activePage === 'Data & exports' && <ExportsPage />}

          <footer className="page-footer">
            <span><span className="footer-mark">p.</span> PEOPLEFLOW <i /> Workforce planning, made clearer.</span>
            <span>Numbers come straight from your planning database.</span>
          </footer>
        </div>
      </section>
    </main>
  );
}

const exceptionGuidance: Record<string, { title: string; category: string; meaning: string; action: string }> = {
  ALLOCATION_EXCEEDS_AVAILABILITY: {
    title: 'Assignment exceeds available hours',
    category: 'Capacity risk',
    meaning: 'An employee has been assigned more hours than they have available for that week, after their schedule and leave are considered.',
    action: 'Review the allocation and rebalance the employee’s work across projects.',
  },
  STALE_SKILL_TREATED_CURRENT: {
    title: 'Skill evidence may be out of date',
    category: 'Skill verification',
    meaning: 'A skill is still marked current even though its last verification is older than the allowed freshness period.',
    action: 'Ask the employee or manager to verify the skill before using it for staffing decisions.',
  },
  DEMAND_DOUBLE_COUNTED: {
    title: 'Project demand may be counted twice',
    category: 'Demand quality',
    meaning: 'Two demand records describe the same project, role, skill, planning week, and version.',
    action: 'Confirm which demand record is correct so the same need is not included twice.',
  },
  OVERLAPPING_PROJECT_ASSIGNMENT: {
    title: 'Employee has concurrent project assignments',
    category: 'Scheduling risk',
    meaning: 'One employee has allocations to multiple projects during the same planning week.',
    action: 'Confirm the assignments fit within the employee’s available hours and resolve any schedule conflict.',
  },
};

function ExceptionsPage({ rows }: { rows: Row[] }) {
  const [openTraceId, setOpenTraceId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const canonicalRows = rows.filter((row) => canonicalExceptionIds.has(String(row.id ?? '')));
  const visibleRows = showAll ? rows : canonicalRows;

  return (
    <section className="exceptions-page">
      <div className="exceptions-intro">
        <div className="exceptions-intro-icon"><ShieldAlert size={20} /></div>
        <div>
          <span className="section-kicker">PLANNING REVIEW</span>
          <h2>{showAll ? `${rows.length.toLocaleString()} detected exceptions` : `${canonicalRows.length} canonical challenge scenarios`}</h2>
          <p>Canonical scenarios are identified by IDs GT-001, GT-002, GT-003 and GT-004. Additional detected records, including stale-skill records, are available in the all-exceptions view.</p>
        </div>
      </div>

      <div role="group" aria-label="Filter exceptions" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button
          className={`button ${showAll ? 'button-light' : 'button-primary'}`}
          type="button"
          aria-pressed={!showAll}
          onClick={() => setShowAll(false)}
        >
          Canonical scenarios ({canonicalRows.length})
        </button>
        <button
          className={`button ${showAll ? 'button-primary' : 'button-light'}`}
          type="button"
          aria-pressed={showAll}
          onClick={() => setShowAll(true)}
        >
          All detected exceptions ({rows.length.toLocaleString()})
        </button>
      </div>

      {visibleRows.length === 0 ? (
        <div className="surface exceptions-empty">
          <Check size={21} />
          <strong>{showAll ? 'No detected exceptions found' : 'No canonical challenge scenarios found'}</strong>
          <p>{showAll ? 'The API returned no exception records.' : 'The API did not return any of the four canonical scenario IDs.'}</p>
        </div>
      ) : (
        <div className="exception-card-grid">
          {visibleRows.map((row) => {
            const issueType = String(row.issue_type ?? '');
            const guidance = exceptionGuidance[issueType] ?? {
              title: issueType.replaceAll('_', ' ').toLowerCase(),
              category: 'Planning review',
              meaning: 'This labelled scenario was included in the synthetic dataset for review.',
              action: 'Review the source record and confirm the appropriate planning decision.',
            };
            const caseId = String(row.id ?? 'CASE');
            const traceId = `exception-trace-${caseId}`;
            const isTraceOpen = openTraceId === caseId;
            return (
              <article className="surface exception-card" key={caseId}>
                <div className="exception-card-top">
                  <span className="exception-category"><ShieldAlert size={14} /> {guidance.category}</span>
                  <span className="exception-case">{caseId}</span>
                </div>
                <h3>{guidance.title}</h3>
                <p className="exception-meaning">{guidance.meaning}</p>
                <div className="exception-action">
                  <span>Suggested review</span>
                  <p>{guidance.action}</p>
                </div>
                <div className="exception-trace">
                  <button
                    className="exception-trace-toggle"
                    type="button"
                    aria-expanded={isTraceOpen}
                    aria-controls={traceId}
                    onClick={() => setOpenTraceId(isTraceOpen ? null : caseId)}
                  >
                    {isTraceOpen ? 'Hide source record' : 'View source record'}
                  </button>
                  {isTraceOpen && <dl id={traceId}>
                    <div><dt>Issue code</dt><dd>{issueType.replaceAll('_', ' ')}</dd></div>
                    <div><dt>Related record</dt><dd>{display(row.entity_id)}</dd></div>
                    <div><dt>Dataset note</dt><dd>{display(row.details)}</dd></div>
                  </dl>}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Overview({
  dashboard,
  gaps,
  exceptions,
  forecasts,
  analysisReady,
  onNavigate,
}: {
  dashboard: Dashboard | null;
  gaps: Row[];
  exceptions: Row[];
  forecasts: Row[];
  analysisReady: boolean;
  onNavigate: (page: string) => void;
}) {
  const utilization = dashboard?.average_utilization ?? 0;
  const ringValue = Math.min(Math.max(utilization, 0), 100);

  return (
    <>
      <section className="welcome-banner">
        <div className="banner-copy">
          <span className="banner-chip"><i /> YOUR PLANNING SNAPSHOT</span>
          <h2>Make room for<br /><em>what’s next.</em></h2>
          <p>Understand where your people are focused and where a little planning can make a big difference.</p>
          <button className="banner-link" onClick={() => onNavigate('Skill gaps')}>Explore skill gaps <ArrowRight size={16} /></button>
        </div>
        <div className="banner-art" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <div className="orbit-core"><Users size={31} strokeWidth={1.5} /></div>
          <span className="orbit-dot dot-one" /><span className="orbit-dot dot-two" /><span className="orbit-dot dot-three" />
          <span className="art-label label-one">PEOPLE <b>{dashboard?.employees?.toLocaleString() ?? '—'}</b></span>
          <span className="art-label label-two">PROJECTS <b>{dashboard?.active_projects ?? '—'}</b></span>
        </div>
        <span className="banner-index">01 — 04</span>
      </section>

      <div className="section-heading">
        <div><span className="section-kicker">AT A GLANCE</span><h2>Your workforce health</h2></div>
        <span className="live-pill"><i /> LIVE FROM YOUR DATABASE</span>
      </div>

      <section className="metric-grid" aria-label="Workforce metrics">
        <MetricCard label="People" value={dashboard?.employees.toLocaleString() ?? '—'} description="In your workforce" icon={<Users size={19} />} color="mint" />
        <MetricCard label="Active projects" value={dashboard?.active_projects ?? '—'} description={`Of ${dashboard?.projects ?? '—'} total projects`} icon={<BriefcaseBusiness size={19} />} color="lilac" />
        <MetricCard label="Unique demand lines with skill gaps" value={dashboard?.skill_gap_records.toLocaleString() ?? '—'} description="Duplicate demand records are excluded from this count." icon={<Activity size={19} />} color="peach" />
        <MetricCard label="Capacity risks" value={dashboard?.overallocated_periods.toLocaleString() ?? '—'} description="Overallocated team-weeks" icon={<ShieldAlert size={19} />} color="butter" />
      </section>

      <section className="insight-grid">
        <article className="surface utilization-card">
          <div className="surface-heading">
            <div><span className="section-kicker">CAPACITY</span><h3>How full is your team?</h3></div>
            <span className="subtle-tag"><Gauge size={14} /> Utilization</span>
          </div>
          <div className="utilization-content">
            <div className="utilization-ring" style={{ '--ring-value': `${ringValue * 3.6}deg` } as React.CSSProperties}>
              <div className="ring-center"><strong>{dashboard ? `${utilization}%` : '—'}</strong><span>in use</span></div>
            </div>
            <div className="utilization-explainer">
              <strong>{utilization > 100 ? 'Capacity needs attention' : utilization >= 85 ? 'Teams are highly engaged' : 'Room to take on more'}</strong>
              <p>Based on allocated hours compared with available hours, after leave and part-time schedules.</p>
              <div className="capacity-key"><span><i className="key-used" /> Allocated time</span><span><i className="key-free" /> Remaining capacity</span></div>
            </div>
          </div>
          <div className="capacity-foot"><span>Workforce capacity overview</span><span>{dashboard?.skills ?? '—'} skills tracked</span></div>
        </article>

        <article className="surface action-card">
          <div className="surface-heading">
            <div><span className="section-kicker">NEXT BEST STEPS</span><h3>A few things to look at</h3></div>
            <span className="action-count">{dashboard?.skill_gap_records ?? exceptions.length}</span>
          </div>
          {!analysisReady ? (
            <div className="action-empty"><span className="empty-spark"><Zap size={17} /></span><strong>Your plan is ready to review</strong><p>Refresh planning to calculate skill gaps and recommended actions.</p></div>
          ) : gaps.length > 0 ? (
            <div className="action-list">
              {gaps.slice(0, 3).map((gap, index) => {
                const gapFte = Number(gap.gap_fte ?? 0);
                const action = gapFte <= 1 ? 'TRAIN' : 'HIRE / TRAIN';
                return <button className="action-item" key={String(gap.id ?? gap.demand_id ?? index)} onClick={() => onNavigate('Skill gaps')}>
                  <span className="action-icon"><Activity size={16} /></span>
                  <span className="action-copy"><strong>Uncovered demand</strong><small>{String(gap.demand_id ?? '').slice(0, 35)} · {gapFte.toFixed(2)} FTE gap</small></span>
                  <span className={`action-badge ${action === 'TRAIN' ? 'badge-train' : 'badge-hire'}`}>{action}</span>
                  <ArrowUpRight size={15} className="action-arrow" />
                </button>;
              })}
            </div>
          ) : (
            <div className="action-empty"><span className="empty-spark"><Check size={17} /></span><strong>Looking good so far</strong><p>No uncovered demand recommendations at this time.</p></div>
          )}
        </article>
      </section>

      <section className="surface forecast-surface" aria-label="Forecast overview">
        <div className="surface-heading gaps-heading">
          <div><span className="section-kicker">FORECAST SIGNALS</span><h3>Demand forecast review</h3><p>Historical demand is used for forecasting. Low-data scenarios are clearly marked as not yet reliable.</p></div>
        </div>
        {forecasts.length === 0 ? (
          <div className="action-empty"><span className="empty-spark"><Activity size={17} /></span><strong>No forecast data available</strong><p>Run the planning analysis to populate demand forecast signals.</p></div>
        ) : (
          <div className="forecast-list" style={{ display: 'grid', gap: '0.85rem' }}>
            {forecasts.slice(0, 4).map((forecast, index) => {
              const confidence = String(forecast.confidence ?? 'UNKNOWN');
              const isReliable = confidence !== 'INSUFFICIENT_DATA';
              const methodology = String(forecast.methodology ?? 'unknown');
              const historyPoints = Number(forecast.history_points ?? 0);
              const forecastFte = Number(forecast.forecast_fte ?? 0);
              return (
                <div key={`${String(forecast.project_id ?? 'project')}-${String(forecast.role_id ?? 'role')}-${String(forecast.skill_id ?? 'skill')}-${index}`} style={{ border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '14px', padding: '0.9rem 1rem', background: 'rgba(15, 23, 42, 0.04)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'center', marginBottom: '0.45rem' }}>
                    <div>
                      <strong style={{ display: 'block', fontSize: '0.95rem' }}>{display(forecast.project_id)}</strong>
                      <small style={{ color: '#64748b' }}>{display(forecast.role_id)} · {display(forecast.skill_id)}</small>
                    </div>
                    <span className={`status-pill ${isReliable ? 'status-ok' : 'status-warning'}`} style={{
                      background: isReliable ? 'rgba(37, 99, 235, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                      color: isReliable ? '#1d4ed8' : '#b45309',
                      borderColor: isReliable ? 'rgba(37, 99, 235, 0.24)' : 'rgba(245, 158, 11, 0.3)',
                    }}>
                      {confidence.replaceAll('_', ' ')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', fontSize: '0.82rem', color: '#334155' }}>
                    <span><strong>Forecast:</strong> {forecastFte.toFixed(2)} FTE</span>
                    <span><strong>History:</strong> {historyPoints} points</span>
                    <span><strong>Method:</strong> {methodology.replaceAll('_', ' ')}</span>
                  </div>
                  <p style={{ margin: '0.65rem 0 0', color: '#475569', lineHeight: 1.5 }}>
                    {isReliable
                      ? 'Enough valid historical demand is available to treat this as a planning forecast.'
                      : 'Not enough valid historical demand is available. This forecast should not be treated as reliable.'}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="surface gaps-surface">
        <div className="surface-heading gaps-heading">
          <div><span className="section-kicker">DEMAND MEETS CAPABILITY</span><h3>Priority skill gaps</h3><p>Start with the demand lines with the biggest capacity shortfall.</p></div>
          <button className="button button-light" onClick={() => onNavigate('Skill gaps')}>See all gaps <ArrowRight size={15} /></button>
        </div>
        <DataTable
          rows={gaps}
          columns={['demand_id', 'required_fte', 'available_fte', 'gap_fte']}
          emptyMessage={analysisReady ? 'No skill gaps to show. Your plan is looking good.' : 'Refresh planning to calculate your current gaps.'}
          compact
        />
      </section>
    </>
  );
}

function MetricCard({
  label,
  value,
  description,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  description: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-topline"><span>{label}</span><span className={`metric-icon ${color}`}>{icon}</span></div>
      <strong className="metric-number">{value}</strong>
      <span className="metric-description">{description}</span>
    </article>
  );
}

function DirectoryPage({
  title,
  description,
  rows,
  columns,
  total,
  offset,
  pageSize,
  changePage,
  search,
  setSearch,
  placeholder,
  emptyMessage,
}: {
  title: string;
  description: string;
  rows: Row[];
  columns: string[];
  total: number;
  offset: number;
  pageSize: number;
  changePage: (offset: number) => void;
  search?: string;
  setSearch?: (value: string) => void;
  placeholder?: string;
  emptyMessage?: string;
}) {
  const firstItem = total === 0 ? 0 : offset + 1;
  const lastItem = Math.min(offset + pageSize, total);
  return (
    <section className="surface directory-surface">
      <div className="surface-heading directory-heading">
        <div><span className="section-kicker">WORKSPACE DIRECTORY</span><h3>{title}</h3><p>{description}</p></div>
        {setSearch && (
          <label className="search-field">
            <Search size={16} />
            <input value={search ?? ''} onChange={(event) => setSearch(event.target.value)} placeholder={placeholder} />
            {search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}
          </label>
        )}
      </div>
      <DataTable rows={rows} columns={columns} emptyMessage={emptyMessage} />
      {pageSize > 0 && total > pageSize && (
        <div className="pagination">
          <span>Showing <strong>{firstItem}–{lastItem}</strong> of <strong>{total.toLocaleString()}</strong></span>
          <div><button onClick={() => changePage(Math.max(0, offset - pageSize))} disabled={offset === 0} aria-label="Previous page"><ChevronLeft size={17} /></button><button onClick={() => changePage(offset + pageSize)} disabled={offset + pageSize >= total} aria-label="Next page"><ChevronRight size={17} /></button></div>
        </div>
      )}
    </section>
  );
}

function DataTable({
  rows,
  columns,
  emptyMessage = 'No records are available yet.',
  compact = false,
}: {
  rows: Row[];
  columns: string[];
  emptyMessage?: string;
  compact?: boolean;
}) {
  return (
    <div className={`table-scroll ${compact ? 'table-compact' : ''}`}>
      <table className="data-table">
        <thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll('_', ' ')}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={String(row.id ?? row.demand_id ?? index)}>
              {columns.map((column, columnIndex) => {
                const value = display(row[column]);
                return (
                  <td key={column} className={columnIndex === 0 ? 'primary-cell' : ''}>
                    {column === 'status' || column === 'action'
                      ? <span className={`status-pill status-${value.toLowerCase().replaceAll(/[^a-z0-9]+/g, '-')}`}>{value.replaceAll('_', ' ')}</span>
                      : column === 'gap_fte'
                        ? <span className="gap-value">{value}</span>
                        : value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <div className="table-empty"><span><Search size={18} /></span>{emptyMessage}</div>}
    </div>
  );
}

function ExportsPage() {
  return (
    <section className="exports-layout">
      <article className="surface export-intro">
        <span className="export-illustration"><ArrowDownToLine size={23} /></span>
        <span className="section-kicker">YOUR DATA, YOUR WAY</span>
        <h3>Everything you need.<br />Nothing complicated.</h3>
        <p>Download a clean CSV file for a spreadsheet, analysis, or sharing with your team. Ground-truth labels are kept in a separate file.</p>
        <div className="export-note"><Check size={15} /> Synthetic data · no personal employee information</div>
      </article>
      <article className="surface export-list-surface">
        <div className="surface-heading"><div><span className="section-kicker">DOWNLOAD CENTER</span><h3>Choose a data file</h3><p>Select only what you need.</p></div></div>
        <div className="export-list">
          {exportNames.map((name, index) => (
            <a className="export-item" href={`${API}/api/exports/${name}`} key={name}>
              <span className={`export-file-icon export-color-${index % 4}`}>CSV</span>
              <span className="export-file-copy"><strong>{name.replaceAll('_', ' ')}</strong><small>{name === 'ground_truth' ? 'Separate challenge labels' : 'Comma-separated values'}</small></span>
              <Download size={16} />
            </a>
          ))}
        </div>
      </article>
    </section>
  );
}

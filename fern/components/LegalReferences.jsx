/**
 * Legal Reference Components for modernized documentation
 * These replace text-based legal typography with visual, interactive elements
 */

// Section Reference Component
export const Section = ({ num, title }) => (
  <span className="section-ref">
    <Badge intent="info" minimal>
      § {num}
    </Badge>
    {title && <span className="section-title">{title}</span>}
  </span>
);

// Statute Citation Component
export const StatuteCite = ({ code = "FAM", section, title }) => (
  <span className="statute-cite">
    <span className="code-badge">{code} Code</span>
    <Badge intent="info" minimal>
      § {section}
    </Badge>
    {title && <span className="statute-title">{title}</span>}
  </span>
);

// Bill Reference Component (AB, SB, etc.)
export const BillRef = ({ type = "AB", num, year }) => (
  <Tooltip tip={`${type} ${num} — Effective ${year}`}>
    <Badge intent="success" minimal>
      {type} {num}
    </Badge>
  </Tooltip>
);

// Case Citation Component
export const CaseCite = ({ name, year, reporter, volume, page, url }) => {
  const Citation = url ? "a" : "span";
  return (
    <Citation href={url} className="case-cite">
      <strong>{name}</strong>
      <span className="case-meta">
        ({year}) {volume} {reporter} {page}
      </span>
    </Citation>
  );
};

// Defined Term with Tooltip
export const DefinedTerm = ({ term, children, definition }) => (
  <Tooltip tip={definition || children}>
    <span className="defined-term" title={definition || children}>
      <em>"{term}"</em>
    </span>
  </Tooltip>
);

// Legislative History Component
export const LegislativeHistory = ({ children, year, type, statute, effective, bill }) => (
  <div className="legislative-history">
    <Icon icon="fa-solid fa-file-contract" size={16} />
    <span className="history-text">
      <strong>{type}</strong> by {statute}
      {bill && <BillRef type={bill.split(" ")[0]} num={bill.split(" ")[1]} />}
      {effective && <span className="effective-date">Effective {effective}</span>}
    </span>
  </div>
);

// Section Range Component (§§ 300–310)
export const SectionRange = ({ from, to, title }) => (
  <span className="section-range">
    <Badge intent="info" minimal>
      §§ {from}–{to}
    </Badge>
    {title && <span className="range-title">{title}</span>}
  </span>
);

// Division/Part Header Component
export const DivisionHeader = ({ number, title, sections, icon }) => (
  <div className="division-header">
    {icon && <Icon icon={icon} size={32} />}
    <div className="division-info">
      <h2>{title}</h2>
      <div className="division-meta">
        <Badge intent="info" minimal>Division {number}</Badge>
        <Badge intent="note" minimal>
          <SectionRange from={sections.split("–")[0]} to={sections.split("–")[1]} />
        </Badge>
      </div>
    </div>
  </div>
);

// Cross-Reference Component
export const CrossRef = ({ href, title, section }) => (
  <a href={href} className="cross-ref">
    <Icon icon="fa-solid fa-arrow-right" size={14} />
    {title || `Section ${section}`}
  </a>
);

// Code Snippet with Legal Context
export const LegalCode = ({ section, subsection, text, amended }) => (
  <div className="legal-code">
    <div className="code-header">
      <Section num={section} />
      {subsection && <span className="subsection">({subsection})</span>}
    </div>
    <div className="code-text">{text}</div>
    {amended && <LegislativeHistory {...amended} />}
  </div>
);

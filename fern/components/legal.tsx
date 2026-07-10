export const Section = ({ num, title }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: '600' }}>
    <span style={{ display: 'inline-block', background: '#1D4ED8', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
      § {num}
    </span>
    {title && <span style={{ fontWeight: '500', marginLeft: '0.25rem' }}>{title}</span>}
  </span>
);

export const StatuteCite = ({ code = "FAM", section, title }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: '500' }}>
    <span style={{ display: 'inline-block', background: 'linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%)', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
      {code}
    </span>
    <span style={{ background: '#1D4ED8', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
      § {section}
    </span>
    {title && <span style={{ marginLeft: '0.25rem' }}>{title}</span>}
  </span>
);

export const SectionRange = ({ from, to, title }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: '600' }}>
    <span style={{ display: 'inline-block', background: '#1D4ED8', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
      §§ {from}–{to}
    </span>
    {title && <span style={{ fontWeight: '500', marginLeft: '0.25rem' }}>{title}</span>}
  </span>
);

export const CaseCite = ({ name, year, reporter, volume, page, url }) => {
  const Component = url ? 'a' : 'span';
  return (
    <Component href={url} style={{ color: '#1D4ED8', textDecoration: 'none', borderBottom: '1px dashed #1D4ED8', cursor: url ? 'pointer' : 'default' }}>
      <strong>{name}</strong>
      <span style={{ color: '#6B7280', fontStyle: 'italic', marginLeft: '0.25rem' }}>
        ({year}) {volume} {reporter} {page}
      </span>
    </Component>
  );
};

export const BillRef = ({ type = "AB", num, year }) => (
  <span style={{ display: 'inline-block', background: '#10B981', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700', marginLeft: '0.5rem' }} title={`${type} ${num} — Effective ${year}`}>
    {type} {num}
  </span>
);

export const LegislativeHistory = ({ type, statute, effective, bill }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', background: 'rgba(29, 78, 216, 0.05)', borderLeft: '3px solid #1D4ED8', borderRadius: '0.375rem', fontSize: '0.875rem', margin: '0.5rem 0', flexWrap: 'wrap' }}>
    <strong>{type}</strong>
    <span>by {statute}</span>
    {bill && <BillRef type={bill.split(" ")[0]} num={bill.split(" ")[1]} />}
    {effective && <span style={{ color: '#6B7280', fontSize: '0.8rem', marginLeft: '0.5rem' }}>Effective {effective}</span>}
  </div>
);

export const DefinedTerm = ({ term, definition, children }) => (
  <span style={{ color: '#1D4ED8', fontStyle: 'italic', borderBottom: '2px dotted #1D4ED8', cursor: 'help' }} title={definition || children}>
    "{term}"
  </span>
);

export const DivisionHeader = ({ number, title, sections, icon }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', padding: '1.5rem', background: 'linear-gradient(135deg, rgba(29, 78, 216, 0.05) 0%, rgba(96, 165, 250, 0.05) 100%)', border: '1px solid #E5E7EB', borderRadius: '0.75rem', margin: '1.5rem 0' }}>
    <div style={{ flex: 1 }}>
      <h2 style={{ margin: '0 0 0.5rem 0', color: '#1D4ED8' }}>{title}</h2>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-block', background: '#1D4ED8', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
          Division {number}
        </span>
        <span style={{ display: 'inline-block', background: '#1D4ED8', color: 'white', padding: '0.25rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.875rem', fontWeight: '700' }}>
          §§ {sections}
        </span>
      </div>
    </div>
  </div>
);

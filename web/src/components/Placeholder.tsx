interface PlaceholderProps {
  fatia: string;
  description: string;
}

export function Placeholder({ fatia, description }: PlaceholderProps) {
  return (
    <div className="samid-card" style={{ marginTop: 24 }}>
      <div className="samid-eyebrow">Em construção · {fatia}</div>
      <h2 className="samid-card-title" style={{ marginTop: 8 }}>
        A ser implementado
      </h2>
      <p style={{ color: 'var(--fg-2)', marginTop: 12 }}>{description}</p>
    </div>
  );
}

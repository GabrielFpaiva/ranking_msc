import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react';

interface UploadDropProps {
  onFile: (file: File) => Promise<void> | void;
  disabled?: boolean;
}

export function UploadDrop({ onFile, disabled }: UploadDropProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pick() {
    inputRef.current?.click();
  }

  async function commit(selected: File | null) {
    if (!selected) return;
    setFile(selected);
    setBusy(true);
    setError(null);
    try {
      await onFile(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (disabled || busy) return;
    const dropped = event.dataTransfer.files?.[0] ?? null;
    void commit(dropped);
  }

  function handleKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Enter' || event.key === ' ') pick();
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    void commit(selected);
    event.target.value = '';
  }

  return (
    <div className="samid-upload">
      <div
        className="samid-drop"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={pick}
        role="button"
        tabIndex={0}
        onKeyDown={handleKey}
      >
        <div className="samid-drop-title">
          {busy ? 'Processando...' : file ? 'Arquivo selecionado' : 'Solte ou clique para escolher o CSV MSC'}
        </div>
        <div className="samid-drop-sub">
          {busy ? 'rodando o motor — aguarde' : 'formato SICONFI · separador ;'}
        </div>
        {file && (
          <div className="samid-drop-file">
            {file.name}
            <span>{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: 'none' }}
          onChange={handleChange}
        />
      </div>
      {error && (
        <div className="samid-pill samid-pill-erro" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

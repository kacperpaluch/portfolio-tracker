import DataPanel from "./DataPanel.jsx";

export default function BackupModal({ backups, onBackup, onClose, busy }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Backup i eksport danych</h2>
          <button onClick={onClose}>Zamknij ✕</button>
        </div>
        <DataPanel backups={backups} onBackup={onBackup} busy={busy} />
      </div>
    </div>
  );
}

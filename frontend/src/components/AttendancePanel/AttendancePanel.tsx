import type { AttendanceStation } from '../../types/ws';
import './AttendancePanel.css';

interface Props {
  stations: AttendanceStation[];
  onClear: () => void;
}

export function AttendancePanel({ stations, onClear }: Props) {
  return (
    <div className="attendance-panel">
      <div className="attendance-header">
        <span className="attendance-title">STATIONS HEARD THIS SESSION</span>
        <button
          className="attendance-clear-btn"
          onClick={onClear}
          disabled={stations.length === 0}
        >
          CLEAR
        </button>
      </div>

      {stations.length === 0 ? (
        <p className="attendance-empty">No stations heard yet.</p>
      ) : (
        <div className="attendance-table-wrap">
          <table className="attendance-table">
            <thead>
              <tr>
                <th>Callsign</th>
                <th>Name</th>
                <th>Location</th>
                <th>GMRS</th>
                <th>HAM</th>
              </tr>
            </thead>
            <tbody>
              {stations.map((s) => (
                <tr key={s.callsign}>
                  <td className="attendance-callsign">{s.callsign}</td>
                  <td>{s.name}</td>
                  <td>{s.location}</td>
                  <td>{s.gmrs}</td>
                  <td>{s.ham}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

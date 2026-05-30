import { useState, useCallback } from 'react';
import { useOperator } from './hooks/useOperator';
import { useWebSocket } from './hooks/useWebSocket';
import type { WsMessage, StatusMsg, TxMessagePayload } from './types/ws';
import { OperatorModal } from './components/OperatorModal/OperatorModal';
import { TopBar } from './components/TopBar/TopBar';
import { ChatDisplay } from './components/ChatDisplay/ChatDisplay';
import type { ChatEntry } from './components/ChatDisplay/ChatDisplay';
import { StatusRow } from './components/StatusRow/StatusRow';
import { MessageInput } from './components/MessageInput/MessageInput';
import './App.css';

let entryCounter = 0;
function nextId() {
  return `msg-${++entryCounter}`;
}

function formatTime(isoOrNow?: string): string {
  const d = isoOrNow ? new Date(isoOrNow) : new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function App() {
  const { operator, setOperator } = useOperator();
  const [showModal, setShowModal] = useState(operator === null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [radioStatus, setRadioStatus] = useState<StatusMsg | null>(null);
  const [transmitting, setTransmitting] = useState(false);

  const handleWsMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'rx_message':
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(msg.ts),
            kind: 'rx',
            sender: msg.from || msg.callsign,
            text: msg.text,
          },
        ]);
        break;

      case 'status':
        setRadioStatus(msg);
        break;

      case 'tx_status':
        setTransmitting(msg.state === 'transmitting');
        break;

      case 'system_msg':
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(),
            kind: 'system',
            text: msg.text,
          },
        ]);
        break;

      case 'contacts':
        // Contacts stored for future use; not rendered in chat
        break;
    }
  }, []);

  const { send, connected } = useWebSocket({ onMessage: handleWsMessage });

  function handleSend(text: string) {
    if (!operator) {
      setShowModal(true);
      return;
    }
    const payload: TxMessagePayload = {
      type: 'tx_message',
      text,
      operator: operator.operatorName,
      callsign: operator.callsign,
    };
    send(payload);
    // Optimistically show outbound message
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        timestamp: formatTime(),
        kind: 'tx',
        sender: operator.callsign,
        text,
      },
    ]);
  }

  const stationStatus = connected ? 'READY' : 'OFFLINE';

  return (
    <div className="app-shell">
      {showModal && (
        <OperatorModal
          initial={operator}
          onSave={(op) => {
            setOperator(op);
            setShowModal(false);
          }}
          onClose={operator ? () => setShowModal(false) : undefined}
        />
      )}

      <TopBar
        stationStatus={stationStatus}
        connected={connected}
        onChangeOperator={() => setShowModal(true)}
      />

      <ChatDisplay entries={messages} />

      <StatusRow status={radioStatus} />

      <MessageInput transmitting={transmitting} onSend={handleSend} />
    </div>
  );
}

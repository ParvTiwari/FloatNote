import { useEffect, useState } from "react";

function App() {
  const [transcript, setTranscript] = useState("");
  const [intent, setIntent] = useState("None");
  const [keywords, setKeywords] = useState([]);
  const [actions, setActions] = useState([]);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/stt");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      setTranscript(prev => prev + " " + data.text);
      setIntent(data.intent);
      setKeywords(data.keywords);

      if (data.intent === "action_item") {
        setActions(prev => [...prev, data.text]);
      }
    };

    ws.onerror = () => {
      console.log("WebSocket connection failed");
    };

    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold mb-6">
        🎤 FloatNote AI Meeting Assistant
      </h1>

      <div className="grid grid-cols-3 gap-6">

        {/* Transcript */}
        <div className="col-span-2 bg-white rounded-xl p-4 shadow h-[500px] overflow-y-auto">
          <h2 className="text-xl font-semibold mb-2">Live Transcript</h2>
          <p>{transcript}</p>
        </div>

        {/* Side Panel */}
        <div className="flex flex-col gap-4">

          <div className="bg-white rounded-xl p-4 shadow">
            <h3 className="font-semibold">Intent</h3>
            <p className={`mt-2 font-bold ${
              intent === "question" ? "text-blue-600" :
              intent === "action_item" ? "text-red-600" :
              intent === "decision" ? "text-green-600" :
              "text-gray-600"
            }`}>
              {intent}
            </p>
          </div>

          <div className="bg-white rounded-xl p-4 shadow">
            <h3 className="font-semibold">Keywords</h3>
            <ul className="mt-2 list-disc list-inside">
              {keywords.map((k, i) => (
                <li key={i}>{k}</li>
              ))}
            </ul>
          </div>

          <div className="bg-white rounded-xl p-4 shadow">
            <h3 className="font-semibold">Action Items</h3>
            <ul className="mt-2 list-disc list-inside">
              {actions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>

        </div>

      </div>
    </div>
  );
}

export default App;

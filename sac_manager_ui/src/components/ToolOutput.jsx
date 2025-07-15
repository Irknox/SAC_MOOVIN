const ToolOutput = ({ tool, output }) => {
  let parsedOutput = {};
  try {
    parsedOutput = JSON.parse(output);  
  } catch (err) {
    return <pre className="text-sm text-red-500">Error parsing JSON</pre>;
  }

  if (tool === "get_package_timeline" && parsedOutput.timeline) {
    return (
      <div className="flex-col z-1000 max-h-auto w-full rounded bg-gray-900 text-gray-200 border border-gray-700">
        <table style={{fontSize:"smaller"}} className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-gray-600">
              <th className="px-1 py-1">FECHA</th>
              <th className="px-1 py-1">ESTADO</th>
            </tr>
          </thead>
          <tbody>
            {parsedOutput.timeline.map((item, idx) => (
              <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800">
                <td className="px-2 py-1 whitespace-nowrap">{item.dateUser}</td>
                <td className="px-2 py-1 whitespace-nowrap">{item.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="max-h-100 max-w-auto bg-gray-900 p-2 text-gray-200 border border-gray-700 text-xs">
      <pre>{JSON.stringify(parsedOutput, null, 2)}</pre>
    </div>
  );
};

export default ToolOutput;
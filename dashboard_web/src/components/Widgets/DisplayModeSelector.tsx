interface DisplayModeSelectorProps<T extends string> {
  modes: { value: T; label: string }[];
  selected: T;
  onChange: (mode: T) => void;
}

export function DisplayModeSelector<T extends string>({
  modes,
  selected,
  onChange,
}: DisplayModeSelectorProps<T>) {
  return (
    <div className="flex gap-1 mt-2">
      {modes.map(({ value, label }) => (
        <button
          key={value}
          onClick={() => onChange(value)}
          title={label}
          className={`px-2 py-0.5 rounded text-xs transition-colors cursor-pointer ${
            selected === value
              ? "bg-blue-600 text-white"
              : "bg-gray-700 text-gray-400 hover:text-white"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

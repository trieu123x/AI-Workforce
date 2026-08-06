import type { ReactNode } from "react";

interface ChatMessageContentProps {
  content: string;
}

function renderInlineMarkdown(value: string, keyPrefix: string): ReactNode[] {
  return value
    .split(/(\*\*.+?\*\*|`[^`\n]+`)/g)
    .filter(Boolean)
    .map((part, index) => {
      const key = `${keyPrefix}-${index}`;

      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={key}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return <code key={key}>{part.slice(1, -1)}</code>;
      }
      return part;
    });
}

export default function ChatMessageContent({ content }: ChatMessageContentProps) {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();

    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push(
        <h3 key={`heading-${index}`}>
          {renderInlineMarkdown(heading[2], `heading-${index}`)}
        </h3>,
      );
      index += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        const item = lines[index].trim().replace(/^[-*]\s+/, "");
        items.push(
          <li key={`bullet-${index}`}>
            {renderInlineMarkdown(item, `bullet-${index}`)}
          </li>,
        );
        index += 1;
      }
      blocks.push(<ul key={`list-${index}`}>{items}</ul>);
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        const item = lines[index].trim().replace(/^\d+\.\s+/, "");
        items.push(
          <li key={`number-${index}`}>
            {renderInlineMarkdown(item, `number-${index}`)}
          </li>,
        );
        index += 1;
      }
      blocks.push(<ol key={`list-${index}`}>{items}</ol>);
      continue;
    }

    const paragraphLines: string[] = [];
    const paragraphStart = index;
    while (
      index < lines.length
      && lines[index].trim()
      && !/^(#{1,3})\s+/.test(lines[index].trim())
      && !/^[-*]\s+/.test(lines[index].trim())
      && !/^\d+\.\s+/.test(lines[index].trim())
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push(
      <p key={`paragraph-${paragraphStart}`}>
        {paragraphLines.map((paragraphLine, lineIndex) => (
          <span key={`line-${paragraphStart}-${lineIndex}`}>
            {lineIndex > 0 && <br />}
            {renderInlineMarkdown(paragraphLine, `line-${paragraphStart}-${lineIndex}`)}
          </span>
        ))}
      </p>,
    );
  }

  return <div className="ai-chat-rich-text">{blocks}</div>;
}

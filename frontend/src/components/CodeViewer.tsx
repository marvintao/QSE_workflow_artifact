// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * CodeViewer component.
 * Uses prism-react-renderer to display the generated quantum Python code with syntax highlighting and line numbers.
 */
import { Highlight, themes } from "prism-react-renderer";
import { useI18n } from "../i18n/useI18n";

/** Props for CodeViewer: `code` is the source string to render; when null, a placeholder hint is shown. */
export interface CodeViewerProps {
  code: string | null;
}

/**
 * Code viewer component.
 * Renders Python code as a read-only block with syntax highlighting and line numbers.
 * Destructuring out `key` and spreading the remaining props is the idiomatic workaround
 * for prism-react-renderer's `key` typing conflict.
 */
export function CodeViewer({ code }: CodeViewerProps) {
  const { t } = useI18n();
  if (!code) {
    return (
      <div className="rounded border border-slate-200 bg-white p-6 text-slate-500">
        {t("code.empty")}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded border border-slate-200 bg-white p-4 text-xs">
      <Highlight code={code} language="python" theme={themes.github}>
        {({ className, style, tokens, getLineProps, getTokenProps }) => (
          <pre className={className} style={style}>
            {tokens.map((line, i) => {
              const { key: _lineKey, ...lineProps } = getLineProps({ line });
              return (
                <div key={i} {...lineProps}>
                  <span className="mr-3 inline-block w-8 select-none text-right text-slate-500">
                    {i + 1}
                  </span>
                  {line.map((token, j) => {
                    const { key: _tokenKey, ...tokenProps } = getTokenProps({ token });
                    return <span key={j} {...tokenProps} />;
                  })}
                </div>
              );
            })}
          </pre>
        )}
      </Highlight>
    </div>
  );
}

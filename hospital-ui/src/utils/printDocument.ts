/**
 * Avinya Isolated Printing Utility
 * Renders statutory slips, wristbands, and clinical summaries in an isolated DOM
 * ensuring only the clinical document is printed, never the application chrome.
 */

export interface PrintDocumentOptions {
  title?: string;
  docType?: "THERMAL_TOKEN" | "WRISTBAND" | "CLINICAL_SUMMARY" | "LAB_REPORT";
}

export function printDocument(htmlContent: string, options: PrintDocumentOptions = {}): void {
  const { title = "Avinya Healthcare Document", docType = "THERMAL_TOKEN" } = options;

  const printWindow = window.open("", "_blank", "width=750,height=800,menubar=no,toolbar=no,location=no,status=no");
  if (!printWindow) {
    // If browser popup blocker intercepts, fallback to browser print with warning
    console.warn("Popup blocked. Falling back to window.print()");
    window.print();
    return;
  }

  const isThermal = docType === "THERMAL_TOKEN";
  const isWristband = docType === "WRISTBAND";

  const customStyles = isThermal
    ? `
      @page { size: 80mm auto; margin: 0; }
      body {
        width: 76mm;
        margin: 0 auto;
        padding: 4mm 2mm;
        font-family: 'Courier New', Courier, monospace;
        font-size: 11px;
        line-height: 1.3;
        color: #000;
        background: #fff;
      }
      .thermal-slip { width: 100%; border: none; }
    `
    : isWristband
    ? `
      @page { size: 280mm 28mm landscape; margin: 0; }
      body {
        margin: 0;
        padding: 4mm 8mm;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 11px;
        color: #000;
        background: #fff;
      }
      .wristband-slip {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        border: 2px solid #000;
        padding: 6px 12px;
        border-radius: 6px;
      }
    `
    : `
      @page { size: A4 portrait; margin: 15mm; }
      body {
        margin: 0;
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.5;
        color: #111;
        background: #fff;
      }
    `;

  printWindow.document.open();
  printWindow.document.write(`
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>${title}</title>
        <style>
          * { box-sizing: border-box; }
          ${customStyles}
          .divider { border-top: 1px dashed #444; margin: 6px 0; }
          .bold { font-weight: bold; }
          .center { text-align: center; }
          .right { text-align: right; }
          .barcode-box {
            letter-spacing: 4px;
            font-family: monospace;
            font-weight: 900;
            background: #eee;
            padding: 4px 8px;
            text-align: center;
            border: 1px solid #999;
            margin: 4px 0;
          }
          @media print {
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          }
        </style>
      </head>
      <body>
        ${htmlContent}
        <script>
          window.onload = function() {
            setTimeout(function() {
              window.focus();
              window.print();
              setTimeout(function() {
                window.close();
              }, 400);
            }, 100);
          };
        </script>
      </body>
    </html>
  `);
  printWindow.document.close();
}


import { HospitalPrinterDevice } from "../core/context/HospitalConfigContext";

/**
 * Avinya Isolated Printing Utility
 * Renders statutory slips, multi-dimension wristbands, thermal tokens, and clinical summaries
 * in an isolated DOM, ensuring only the target clinical document is printed, never application chrome.
 */

export interface WristbandPrintConfig {
  widthMm?: number; // e.g. 280, 250, 180, 150, 100
  heightMm?: number; // e.g. 25, 28, 19, 15, 12
  printableLengthMm?: number; // e.g. 75mm (the face information clip area)
  orientation?: "landscape" | "portrait";
  printerType?: "ZEBRA_HC100" | "DIRECT_THERMAL_ROLL" | "LASER_SHEETLET" | "STANDARD_POS";
  fontScale?: "small" | "medium" | "large";
}

export interface ThermalPrintConfig {
  rollWidthMm?: number; // 58, 80, 112, or custom
}

export interface PrintDocumentOptions {
  title?: string;
  docType?: "THERMAL_TOKEN" | "WRISTBAND" | "CLINICAL_SUMMARY" | "LAB_REPORT";
  wristbandConfig?: WristbandPrintConfig;
  thermalConfig?: ThermalPrintConfig;
  printerDevice?: HospitalPrinterDevice;
}

export function printDocument(htmlContent: string, options: PrintDocumentOptions = {}): void {
  const {
    title = "Avinya Healthcare Document",
    docType = "THERMAL_TOKEN",
    wristbandConfig = {},
    thermalConfig = {},
    printerDevice,
  } = options;

  if (printerDevice) {
    console.info(
      `[Avinya Hardware Dispatch] Printing '${title}' on '${printerDevice.name}' via ${printerDevice.connectionType} ` +
      `(${printerDevice.ipAddress ? `${printerDevice.ipAddress}:${printerDevice.port || 9100}` : "Direct Attached"}) ` +
      `Protocol: ${printerDevice.protocol} Media: ${printerDevice.mediaWidthMm}x${printerDevice.mediaHeightMm || "Roll"}mm`
    );
  }

  const printWindow = window.open("", "_blank", "width=780,height=850,menubar=no,toolbar=no,location=no,status=no");
  if (!printWindow) {
    console.warn("Popup blocked. Falling back to window.print()");
    window.print();
    return;
  }

  const isThermal = docType === "THERMAL_TOKEN" || (printerDevice && printerDevice.targetCategory === "THERMAL_TOKEN");
  const isWristband = docType === "WRISTBAND" || (printerDevice && printerDevice.targetCategory === "WRISTBAND");
  const isLabLabel = docType === "LAB_REPORT" || (printerDevice && printerDevice.targetCategory === "LAB_LABEL");

  // Dynamic Thermal Sizing
  const rollWidth = printerDevice?.mediaWidthMm || thermalConfig.rollWidthMm || 80;
  const contentWidth = Math.max(48, rollWidth - 4);

  // Dynamic Wristband Sizing (defaults to Adult 280x25mm if unspecified)
  const wbWidth = printerDevice?.mediaWidthMm || wristbandConfig.widthMm || 280;
  const wbHeight = printerDevice?.mediaHeightMm || wristbandConfig.heightMm || 25;
  const wbPrintableLength = printerDevice?.printableHeightMm || printerDevice?.printableWidthMm || wristbandConfig.printableLengthMm || Math.min(wbWidth, 80);
  const wbOrientation = printerDevice ? printerDevice.orientation.toLowerCase() as "landscape" | "portrait" : (wristbandConfig.orientation || "landscape");
  const isZebraVertical = (printerDevice?.name.toLowerCase().includes("zebra") || wristbandConfig.printerType === "ZEBRA_HC100" || wbOrientation === "portrait");

  const customStyles = isThermal
    ? `
      @page {
        size: ${rollWidth}mm auto;
        margin: ${printerDevice?.marginTopMm || 0}mm ${printerDevice?.marginRightMm || 0}mm ${printerDevice?.marginBottomMm || 0}mm ${printerDevice?.marginLeftMm || 0}mm;
      }
      body {
        width: ${contentWidth}mm;
        margin: 0 auto;
        padding: 3mm 2mm;
        font-family: 'Courier New', Courier, monospace;
        font-size: ${rollWidth <= 58 ? "9px" : "11px"};
        line-height: 1.25;
        color: #000;
        background: #fff;
      }
      .thermal-slip { width: 100%; border: none; }
    `
    : isWristband
    ? `
      @page {
        size: ${isZebraVertical ? `${wbHeight}mm ${wbWidth}mm portrait` : `${wbWidth}mm ${wbHeight}mm landscape`};
        margin: ${printerDevice?.marginTopMm || 0}mm ${printerDevice?.marginRightMm || 0}mm ${printerDevice?.marginBottomMm || 0}mm ${printerDevice?.marginLeftMm || 0}mm;
      }
      body {
        margin: 0;
        padding: 2mm 4mm;
        width: ${wbWidth}mm;
        height: ${wbHeight}mm;
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: ${wbHeight <= 15 ? "8px" : wbHeight <= 19 ? "9px" : "11px"};
        line-height: 1.15;
        color: #000;
        background: #fff;
        display: flex;
        align-items: center;
      }
      .wristband-slip {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #000;
        padding: 2mm 4mm;
        border-radius: 4px;
        width: ${wbPrintableLength}mm;
        max-width: 100%;
        height: calc(${wbHeight}mm - 4mm);
        box-sizing: border-box;
        overflow: hidden;
      }
      .wristband-full {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .allergy-tag {
        color: #dc2626;
        font-weight: 900;
        text-transform: uppercase;
        border: 1px solid #dc2626;
        padding: 1px 3px;
        border-radius: 2px;
      }
    `
    : isLabLabel
    ? `
      @page {
        size: ${printerDevice ? `${printerDevice.mediaWidthMm}mm ${printerDevice.mediaHeightMm}mm ${printerDevice.orientation.toLowerCase()}` : "50mm 25mm landscape"};
        margin: ${printerDevice?.marginTopMm || 1}mm ${printerDevice?.marginRightMm || 2}mm ${printerDevice?.marginBottomMm || 1}mm ${printerDevice?.marginLeftMm || 2}mm;
      }
      body {
        margin: 0;
        padding: 2px 4px;
        width: ${printerDevice?.mediaWidthMm || 50}mm;
        height: ${printerDevice?.mediaHeightMm || 25}mm;
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 8px;
        line-height: 1.1;
        color: #000;
        background: #fff;
      }
    `
    : `
      @page {
        size: ${printerDevice ? `${printerDevice.mediaWidthMm}mm ${printerDevice.mediaHeightMm}mm ${printerDevice.orientation.toLowerCase()}` : "A4 portrait"};
        margin: ${printerDevice?.marginTopMm ? `${printerDevice.marginTopMm}mm` : "15mm"};
      }
      body {
        margin: 0;
        padding: 18px;
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
          .divider { border-top: 1px dashed #444; margin: 5px 0; }
          .bold { font-weight: bold; }
          .center { text-align: center; }
          .right { text-align: right; }
          .barcode-box {
            letter-spacing: 2px;
            font-family: monospace;
            font-weight: 900;
            background: #eee;
            padding: 2px 4px;
            text-align: center;
            border: 1px solid #999;
            margin: 2px 0;
            display: inline-block;
          }
          @media print {
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          }
        </style>
      </head>
      <body>
        ${htmlContent}
        <script>
          window.addEventListener('load', function() {
            setTimeout(function() {
              window.focus();
              window.print();
              setTimeout(function() { window.close(); }, 750);
            }, 300);
          });
        </script>
      </body>
    </html>
  `);
  printWindow.document.close();
}

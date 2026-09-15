export function syntheticPdf(pageTexts: string[]): Buffer {
  const fontObject = 3 + pageTexts.length * 2;
  const pageReferences = pageTexts.map((_, index) => `${3 + index * 2} 0 R`).join(" ");
  const objects = new Map<number, string>([
    [1, "<< /Type /Catalog /Pages 2 0 R >>"],
    [2, `<< /Type /Pages /Kids [${pageReferences}] /Count ${pageTexts.length} >>`],
    [fontObject, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"],
  ]);

  pageTexts.forEach((text, index) => {
    const pageObject = 3 + index * 2;
    const contentObject = pageObject + 1;
    const escaped = text.replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
    const commands = text ? `BT /F1 12 Tf 72 720 Td (${escaped}) Tj ET` : "BT ET";
    objects.set(
      pageObject,
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] `
        + `/Resources << /Font << /F1 ${fontObject} 0 R >> >> /Contents ${contentObject} 0 R >>`,
    );
    objects.set(contentObject, `<< /Length ${Buffer.byteLength(commands)} >>\nstream\n${commands}\nendstream`);
  });

  let pdf = "%PDF-1.4\n";
  const offsets = new Map<number, number>();
  for (let objectNumber = 1; objectNumber <= fontObject; objectNumber += 1) {
    offsets.set(objectNumber, Buffer.byteLength(pdf));
    pdf += `${objectNumber} 0 obj\n${objects.get(objectNumber)}\nendobj\n`;
  }
  const xrefOffset = Buffer.byteLength(pdf);
  pdf += `xref\n0 ${fontObject + 1}\n0000000000 65535 f \n`;
  for (let objectNumber = 1; objectNumber <= fontObject; objectNumber += 1) {
    pdf += `${String(offsets.get(objectNumber)).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${fontObject + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(pdf, "ascii");
}

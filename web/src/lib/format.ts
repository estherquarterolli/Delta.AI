/** Formata uma data ISO como "dd/mm" (pt-BR), usado em "com base no seu
 * peso de dd/mm". */
export function formatarDataCurta(isoDate: string): string {
  const data = new Date(isoDate);
  const dia = String(data.getDate()).padStart(2, "0");
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  return `${dia}/${mes}`;
}

/** Formata uma data ISO como "dd/mm/aaaa" (pt-BR), usado em listagens. */
export function formatarData(isoDate: string): string {
  const data = new Date(isoDate);
  return data.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Formata uma data ISO como "dd/mm/aaaa às HH:mm" (pt-BR). */
export function formatarDataHora(isoDate: string): string {
  const data = new Date(isoDate);
  const dataFormatada = data.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  const horaFormatada = data.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${dataFormatada} às ${horaFormatada}`;
}

/** Formata um peso em kg com 1 decimal, ex.: 70.5 -> "70,5 kg". */
export function formatarPeso(pesoKg: number): string {
  return `${pesoKg.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kg`;
}

/** Converte um `Date` local para o valor esperado por um
 * `<input type="datetime-local">` (sem timezone, minutos de precisão). */
export function paraInputDatetimeLocal(data: Date): string {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  const hora = String(data.getHours()).padStart(2, "0");
  const minuto = String(data.getMinutes()).padStart(2, "0");
  return `${ano}-${mes}-${dia}T${hora}:${minuto}`;
}

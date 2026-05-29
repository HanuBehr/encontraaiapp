import type { Locale } from "@/lib/i18n/translations";

const EXACT_EN: Record<string, string> = {
  "Motivo": "Reason",
  "Corresponde a uma regra de exclusão ativa.": "Matches an active exclusion rule.",
  "Bloqueado": "Blocked",
  "Não informado": "Not provided",
  "Não disponível": "Not available",
  "Responsável e classificação": "Assignee and classification",
  "Responsável": "Assignee",
  "Região": "Region",
  "Regra de atribuição": "Assignment rule",
  "Atribuído em": "Assigned at",
  "Operação": "Operation",
  "Último enriquecimento": "Last enrichment",
  "Última página": "Last page",
  "Último status": "Last status",
  "Duplicado": "Duplicate",
  "Histórico": "History",
  "Evidências": "Evidence",
  "Leads com falha": "Failed leads",
  "Arquivo": "File",
  "Solicitados": "Requested",
  "Processados": "Processed",
  "Concluídos": "Completed",
  "Novos contatos": "New contacts",
  "Canais públicos": "Public channels",
  "Formulários": "Forms",
  "Ignorados": "Skipped",
  "Erros": "Errors",
  "Preenchidos": "Filled",
  "Precisam revisão": "Need review",
  "Sem correspondência": "No match",
  "Já tinham CNPJ": "Already had CNPJ",
  "Aguardando revisão": "Waiting for review",
  "Busca paga recente": "Recent paid search",
  "Consultados agora": "Consulted now",
  "Consultas pagas": "Paid calls",
  "Duplicadas evitadas": "Duplicates avoided",
  "Atualizados": "Updated",
  "IDs ausentes": "Missing IDs",
  "Leads": "Leads",
  "Aprovado manualmente.": "Approved manually.",
  "Candidato em revisão": "Candidate under review",
  "Melhor candidato encontrado": "Best candidate found",
  "Possível CNPJ": "Possible CNPJ",
  "Razão Social": "Legal name",
  "Nome Fantasia": "Trade name",
  "Modo da busca": "Search mode",
  "Cidade/UF": "City/state",
  "Atividade/CNAE": "Activity/CNAE",
  "Telefone(s)": "Phone(s)",
  "Email(s)": "Email(s)",
  "Endereço": "Address",
  "Confiança": "Confidence",
  "Pontuação": "Score",
  "Provedor": "Provider",
  "Critérios do match": "Match criteria",
  "Exportação pronta para prospecção. O arquivo Excel já foi baixado no seu navegador.": "Export ready for prospecting. The Excel file has already been downloaded in your browser.",
  "Alguns leads falharam, mas a API não retornou os IDs.": "Some leads failed, but the API did not return their IDs.",
};

export function translateLooseText(value: string, locale: Locale) {
  if (locale === "pt-BR") {
    return value;
  }

  const exact = EXACT_EN[value];
  if (exact) {
    return exact;
  }

  return value
    .replace("Enriquecimento concluído com alertas", "Enrichment completed with warnings")
    .replace("Enriquecimento concluído", "Enrichment completed")
    .replace("Enriquecimento CNPJ concluído com alertas", "CNPJ enrichment completed with warnings")
    .replace("Enriquecimento CNPJ concluído", "CNPJ enrichment completed")
    .replace("Atribuição concluída", "Assignment completed")
    .replace("Planilha baixada", "Spreadsheet downloaded")
    .replace("Última importação", "Latest import");
}

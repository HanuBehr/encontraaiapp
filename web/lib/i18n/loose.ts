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
  "Aprovando...": "Approving...",
  "Aprovar este CNPJ": "Approve this CNPJ",
  "Manter sem CNPJ": "Keep without CNPJ",
  "Atualizando...": "Updating...",
  "A busca encontrou um candidato, mas precisa de revisão manual.": "The lookup found a candidate that needs manual review.",
  "Mais de um candidato forte encontrado. Escolha o cadastro correto.": "More than one strong candidate was found. Choose the correct registration.",
  "Candidato encontrado. Revise e aprove antes de consultar novamente.": "Candidate found. Review and approve before searching again.",
  "CNPJ não encontrado no site.": "CNPJ not found on the website.",
  "Este lead não tem site público para consulta de CNPJ.": "This lead has no public website for CNPJ lookup.",
  "Site sem resposta.": "Website did not respond.",
  "O site demorou demais para responder.": "The website took too long to respond.",
  "Consulta pública limitada/rate limit.": "Public lookup rate limited.",
  "Busca cadastral paga não configurada.": "Paid company search is not configured.",
  "A CNPJá não retornou candidatos para este lead.": "CNPJa returned no candidates for this lead.",
  "Nenhum candidato encontrado na busca cadastral.": "No candidate found in company registry search.",
  "A busca cadastral encontrou candidatos, mas sem confiança suficiente para preencher automaticamente.": "Company registry search found candidates, but confidence was too low for automatic filling.",
  "Possível CNPJ encontrado na busca cadastral, precisa revisão.": "Possible CNPJ found in company registry search; review is required.",
  "Busca cadastral temporariamente limitada pelo provedor.": "Company registry search is temporarily limited by the provider.",
  "Busca cadastral pausada por limite do provedor. Tente novamente em cerca de 1 minuto.": "Company registry search paused by provider limit. Try again in about 1 minute.",
  "Falha temporária na busca cadastral paga.": "Temporary failure in paid company registry search.",
  "Falha temporária na consulta pública de CNPJ.": "Temporary failure in public CNPJ lookup.",
  "Um CNPJ foi encontrado, mas a validação pública não confirmou a empresa.": "A CNPJ was found, but public validation did not confirm the company.",
  "Um possível CNPJ foi encontrado, mas sem confiança suficiente para preencher automaticamente.": "A possible CNPJ was found, but confidence was too low for automatic filling.",
  "Busca paga já feita recentemente para este lead. Resultado anterior preservado para evitar gastar créditos de novo.": "Paid search was already run recently for this lead. The previous result was preserved to avoid spending credits again.",
  "Aprovado manualmente.": "Approved manually.",
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

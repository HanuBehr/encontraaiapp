const LABELS: Record<string, string> = {
  new: "Novo",
  reviewed: "Revisado",
  approved: "Aprovado",
  contacted: "Contatado",
  replied: "Respondeu",
  interested: "Interessado",
  closed: "Fechado",
  not_interested: "Sem interesse",
  do_not_contact: "Não contatar",
  google_places: "Google Places",
  website: "Site",
  manual_import: "Importação manual",
  demo_seed: "Demo",
  merged: "Mesclado",
  ideal_sme: "PME ideal",
  possible_sme: "PME possível",
  large_enterprise: "Grande empresa",
  unknown: "Não classificado",
  varejo: "Varejo",
  atacado: "Atacado",
  distribuidora: "Distribuidora",
  ecommerce: "E-commerce",
  industria: "Indústria",
  construcao_civil: "Construção civil",
  enriched: "Enriquecimento",
  assigned: "Atribuição",
  imported: "Importação",
  created: "Criação",
  blocked: "Bloqueio",
  unblocked: "Desbloqueio",
  updated: "Atualização",
  email: "Email",
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  phone: "Telefone",
  contact_form: "Formulário",
  contact_page: "Página de contato",
  homepage: "Página inicial",
  about_page: "Página institucional",
  page: "Página",
};

export function formatLeadLabel(value?: string | null) {
  if (!value) {
    return null;
  }
  return LABELS[value] ?? value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

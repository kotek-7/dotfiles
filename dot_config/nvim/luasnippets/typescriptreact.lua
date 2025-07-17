local ls = require("luasnip")
local s = ls.snippet
local t = ls.text_node
local i = ls.insert_node

return {
  s("comp", {
    t("export default function "), i(1, "Component"), t("() {"), t({ "", "" }),
    t("\t"), t("return ("), t({ "", "" }),
    t("\t\t"), i(0), t({ "", "" }),
    t("\t"), t(");"), t({ "", "" }),
    t("}")
  }),

  s("class", {
    t('className="'), i(0), t('"')
  }),

  s("compprops", {
    t("interface Props {"), t({ "", "" }),
    t("\t"), i(2), t({ "", "" }),
    t("}"), t({ "", "" }),
    t({ "", "" }),
    t("export default function "), i(1, "Component"), t("(props: Props) {"), t({ "", "" }),
    t("\t"), t("return ("), t({ "", "" }),
    t("\t\t"), i(0), t({ "", "" }),
    t("\t"), t(");"), t({ "", "" }),
    t("}")
  }),
}

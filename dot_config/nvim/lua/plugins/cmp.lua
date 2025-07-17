return {
  { "hrsh7th/cmp-nvim-lsp", lazy = true, event = { "InsertEnter", "CmdlineEnter" }  },
  { "hrsh7th/cmp-buffer", lazy = true, event = { "InsertEnter", "CmdlineEnter" }  },
  { "hrsh7th/cmp-path", lazy = true, event = { "InsertEnter", "CmdlineEnter" } },
  { "hrsh7th/cmp-cmdline", lazy = true, event = { "InsertEnter", "CmdlineEnter" } },
  { "saadparwaiz1/cmp_luasnip", lazy = true, event = { "InsertEnter", "CmdlineEnter" } },
  { "L3MON4D3/LuaSnip", lazy = true, event = { "InsertEnter", "CmdlineEnter" } },
  { "onsails/lspkind-nvim", lazy = true, event = { "InsertEnter", "CmdlineEnter" } },
  {
    "zbirenbaum/copilot-cmp",
    lazy = true,
    config = function()
      require("copilot_cmp").setup()
    end
  },
  {
    "hrsh7th/nvim-cmp",
    lazy = true,
    event = { "InsertEnter", "CmdlineEnter" },
    config = function()
      local cmp = require("cmp")
      local luasnip = require("luasnip")

      cmp.setup({
        preselect = cmp.PreselectMode.None,
        formatting = {
          format = require("lspkind").cmp_format {
            mode = "symbol",
            preset = "codicons",
            symbol_map = {
              Copilot = "",
            }
          }
        },
        snippet = {
          expand = function(args)
            require('luasnip').lsp_expand(args.body)
          end,
        },
        mapping = cmp.mapping.preset.insert({
          ['<C-b>'] = cmp.mapping.scroll_docs(-4),
          ['<C-f>'] = cmp.mapping.scroll_docs(4),
          ['<C-Space>'] = cmp.mapping.complete(),
          ['<C-e>'] = cmp.mapping.abort(),
          ['<CR>'] = cmp.mapping(function(fallback)
            if cmp.visible() then
              if luasnip.expandable() then
                luasnip.expand()
              else
                cmp.confirm();
              end
            else
              fallback()
            end
          end),

          ["<Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_next_item()
            elseif luasnip.locally_jumpable(1) then
              luasnip.jump(1)
            else
              fallback()
            end
          end, { "i", "s" }),

          ["<S-Tab>"] = cmp.mapping(function(fallback)
            if cmp.visible() then
              cmp.select_prev_item()
            elseif luasnip.locally_jumpable(-1) then
              luasnip.jump(-1)
            else
              fallback()
            end
          end, { "i", "s" }),

        }),
        sources = cmp.config.sources {
          { name = 'luasnip' },
          { name = 'nvim_lsp' },
          { name = 'path' },
          { name = 'buffer' },
          { name = "copilot" },
        },
      })

      -- Use buffer source for `/` and `?` (if you enabled `native_menu`, this won't work anymore).
      cmp.setup.cmdline({ '/', '?' }, {
        mapping = cmp.mapping.preset.cmdline(),
        sources = {
          { name = 'buffer' }
        }
      })

      -- Use cmdline & path source for ':' (if you enabled `native_menu`, this won't work anymore).
      cmp.setup.cmdline(':', {
        mapping = cmp.mapping.preset.cmdline(),
        sources = cmp.config.sources({
          { name = 'path' },
          { name = 'cmdline' },
        }),
        matching = { disallow_symbol_nonprefix_matching = false }
      })

      cmp.event:on(
        'confirm_done',
        require('nvim-autopairs.completion.cmp').on_confirm_done()
      )
    end,
  }
}

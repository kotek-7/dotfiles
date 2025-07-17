return {
  { "williamboman/mason.nvim", lazy = true },
  { "neovim/nvim-lspconfig", lazy = true },
  {
    "williamboman/mason-lspconfig.nvim",
    lazy = true,
    event = { "BufReadPre", "BufNewFile" },
    config = function()
      vim.api.nvim_create_autocmd("LspAttach", {
        group = vim.api.nvim_create_augroup("lsp-attach", {}),
        callback = function(event)
          vim.keymap.set('n', '<leader>cd', "<cmd>Lspsaga show_line_diagnostics<cr>", { buffer = event.buf, desc = "Show diagnostic" })
          vim.keymap.set('n', ']d', "<cmd>Lspsaga diagnostic_jump_next<cr>", { buffer = event.buf, desc = "Next Diagnostic"})
          vim.keymap.set('n', '[d', "<cmd>Lspsaga diagnostic_jump_prev<cr>", { buffer = event.buf, desc = "Prev Diagnostic"})
          vim.keymap.set('n', 'gd', '<cmd>Lspsaga peek_definition<CR>', { buffer = event.buf, desc = "Goto Definition" })
          vim.keymap.set('n', 'gD', '<cmd>Lspsaga peek_type_definition<CR>', { buffer = event.buf, desc = "Goto Type Declaration" })
          vim.keymap.set('n', 'gr', '<cmd>Lspsaga finder<CR>', { buffer = event.buf, desc = "Goto Reference" })
          vim.keymap.set('n', 'gi', require("telescope.builtin").lsp_implementations, { buffer = event.buf, desc = "Goto Implementation" })
          vim.keymap.set('n', 'K', '<cmd>Lspsaga hover_doc<CR>', { buffer = event.buf, desc = 'Hover Documentation' })
          vim.keymap.set('n', '<leader>cf', function() vim.lsp.buf.format({ async = true }) end, { buffer = event.buf, desc = 'Code Format' })
          vim.keymap.set('n', '<leader>ca', '<cmd>Lspsaga code_action<CR>', { buffer = event.buf, desc = 'Code Action' })
          vim.keymap.set('n', '<leader>cr', '<cmd>Lspsaga rename<CR>', { buffer = event.buf, desc = 'Rename' })
        end,
      })

      local capabilities = vim.tbl_deep_extend(
        "force",
        vim.lsp.protocol.make_client_capabilities(),
        {},
        require("cmp_nvim_lsp").default_capabilities()
      )

      require("mason-lspconfig").setup({
        ensure_installed = {
          "lua_ls",
          "tsserver",
          "html",
          "cssls",
          "tailwindcss",
          "eslint"
        },
      })
      require("mason-lspconfig").setup_handlers({
        function(server_name)
          require("lspconfig")[server_name].setup({
            capabilities = capabilities,
          })
        end,

        ["tsserver"] = function()
          require("lspconfig").tsserver.setup({
            init_options = {},
            filetypes = {
              "javascript",
              "typescript",
              "typescriptreact",
              "typescript.tsx",
              "vue",
            },
          })
        end,

        ["arduino_language_server"] = function()
          require("lspconfig").arduino_language_server.setup({
            cmd = {
              "arduino-language-server",
              "-cli-config",
              '"C:/Users/kotek/AppData/Local/Arduino15/arduino-cli.yaml"',
            }
          })
        end,

        ["lua_ls"] = function()
          local lspconfig = require("lspconfig")

          ---@param names string[]
          ---@return string[]
          local function get_plugin_paths(names)
            local plugins = require("lazy.core.config").plugins
            local paths = {}
            for _, name in ipairs(names) do
              if plugins[name] then
                table.insert(paths, plugins[name].dir .. "/lua")
              else
                vim.notify("Invalid plugin name: " .. name)
              end
            end
            return paths
          end

          ---@param plugins string[]
          ---@return string[]
          local function library(plugins)
            local paths = get_plugin_paths(plugins)
            table.insert(paths, vim.fn.stdpath("config") .. "/lua")
            table.insert(paths, vim.env.VIMRUNTIME .. "/lua")
            table.insert(paths, "${3rd}/luv/library")
            table.insert(paths, "${3rd}/busted/library")
            table.insert(paths, "${3rd}/luassert/library")
            return paths
          end

          lspconfig.lua_ls.setup({
            settings = {
              Lua = {
                runtime = {
                  version = "LuaJIT",
                  pathStrict = true,
                  path = { "?.lua", "?/init.lua" },
                },
                workspace = {
                  library = library({ "lazy.nvim", "telescope-frecency.nvim" }),
                  checkThirdParty = "Disable",
                },
              },
            },
          })
        end
      })
    end,
  },
  {
    "nvimdev/lspsaga.nvim",
    opts = {},
  },
}

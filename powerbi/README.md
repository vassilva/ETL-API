# ETL-API Management Dashboard (Power BI Project)

A source-controlled Power BI Project (PBIP) on top of the read-only BI semantic layer
(`sql/create_bi_views.sql`). The semantic model is stored as **TMDL** and the report as
**PBIR** (enhanced report format), so every table, relationship, measure, page and visual
is plain text reviewed in Git.

```text
powerbi/
├── ETL-API.pbip                    open this file in Power BI Desktop
├── ETL-API.SemanticModel/          TMDL: 3 tables (bi views), 2 relationships, 11 measures
└── ETL-API.Report/                 PBIR: 2 pages, theme in StaticResources/RegisteredResources
```

## Model

| Table | Source | Grain |
|---|---|---|
| `fact_cart_item` | `bi.fact_cart_item` | one product line inside one cart |
| `dim_product` | `bi.dim_product` | one product (current snapshot) |
| `dim_customer` | `bi.dim_customer` | one customer (no email/phone) |

Relationships: `dim_product[product_id]` 1 → * `fact_cart_item[product_id]` and
`dim_customer[user_id]` 1 → * `fact_cart_item[user_id]`; single direction, active.
Only the three `bi` views are modeled (never the `public` base tables), Import mode.

Measures (display folders): *Cart Value* (Cart Value, Discounted Value, Discount Value,
Discount %, Avg Cart Value, Median Cart Value), *Carts & Quantity* (Carts, Quantity in Carts,
Units), *Inventory* (Current Stock, Stock Coverage). Implicit measures are disabled and the
`stock` column is hidden, so stock can only be used through `[Current Stock]`, which reads
`dim_product` and is never aggregated through cart lines.

Semantics (the data has no dates and no checkout or payment status):

- **Cart Value** is the value of cart lines, not confirmed revenue.
- **Quantity in Carts** is units represented in customer carts, not units sold.
- **Current Stock** is the current stock snapshot, not historical inventory.
- There is no time dimension; every page is a snapshot.

## Opening the project

Prerequisites: Power BI Desktop (validated with 2.157, August 2026), the `bi` views
(`sql/create_bi_views.sql`), the read-only login (`sql/create_bi_reader_role.sql`) with a
password set locally, and a completed ETL Load.

1. Open `powerbi/ETL-API.pbip` in Power BI Desktop.
2. The first time, Power BI asks for credentials for the PostgreSQL source: choose
   **Database** authentication with user `powerbi_reader` (if already entered once on
   this machine for the same server/database, Desktop reuses them).
3. Select **Refresh** to import the data (Import mode; about 1.2k rows).

The server and database are the model parameters `PostgreSQL Server` and
`PostgreSQL Database` (Transform data > Edit parameters). **No credential is stored in the
project**: Power BI keeps them in the user's local credential store. Desktop's local state
(`.pbi/localSettings.json`, `.pbi/cache.abf`) is git-ignored.

## Editing

Edit in Power BI Desktop and save (PBIP), or edit the text files. If a file is edited by
hand, keep **UTF-8 without BOM**: Power BI Desktop refuses to open a PBIR file that starts
with a BOM (UTF-8 signature; observed with Desktop 2.157). The PBIR files reference the official
Microsoft JSON schemas (`$schema`), so they can be validated with any JSON Schema validator.

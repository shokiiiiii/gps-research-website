
flowchart TD
    subgraph S1["① 滞在抽出"]
        A["GPS Trip Data"] --> B["Python：確認中"]
        B --> C[("Stay Data")]
    end

    subgraph S2["② 建物付与"]
        D[("建物ポリゴン")]
        E["Processed_Stay_Zmap_TOWN_II.py"]
        F[("Stay + 建物情報")]
        C --> E
        D --> E
        E --> F
    end

    subgraph S3["③ 共滞在分析"]
        G["Python：確認中"]
        H[("Co-stay Data")]
        F --> G --> H
    end

    F -.-> I["検証：Stay_region_building.ipynb"]
    H -.-> J["検証Notebook：確認中"]

    classDef data fill:#E0F2FE,stroke:#0284C7,color:#075985
    classDef script fill:#F1F5F9,stroke:#64748B,color:#334155
    classDef check fill:#DCFCE7,stroke:#16A34A,color:#166534

    class A,C,D,F,H data
    class B,E,G script
    class I,J check

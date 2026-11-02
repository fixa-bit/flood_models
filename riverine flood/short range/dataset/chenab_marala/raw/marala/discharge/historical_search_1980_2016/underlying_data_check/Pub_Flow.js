'use strict';
let swiper;
// Register the plugin to all charts:
Chart.register(ChartDataLabels);
const equals = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const DisplayFromate = "DD-MM-YYYY";
function getPercent(v) {
    if (v == "NaN") {
        return "";
    }
    else { return v + "%" }
}
  
function UpdateFlowStats(flowData) {
    if (!flowData) return;

    const config = [
        { key: "tarbela", selector: "#Tarbela", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Tarbela" },
        { key: "mangla", selector: "#Mangla", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Mangla" },
        { key: "kalabagh", selector: "#Kalabagh", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Kalabagh" },
        { key: "chashma", selector: "#Chashma", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Chashma" },
        { key: "taunsa", selector: "#Taunsa", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Taunsa" },
        { key: "marala", selector: "#Marala", fields: ["Inflow", "Outflow"], fallback: "Reservoir.Marala" },
        { key: "gudduBarrage", selector: "#GudduBarrage", fields: ["US", "DS"], fallback: "GudduSummary" },
        { key: "sukkurBarrage", selector: "#SukkurBarrage", fields: ["US", "DS"], fallback: "SukkurSummary" },
        { key: "kotriBarrage", selector: "#KotriBarrage", fields: ["US", "DS"], fallback: "KotriSummary" }
    ];

    // Helper to safely access nested properties
    function getNestedValue(obj, path) {
        return path.split('.').reduce((acc, key) => acc?.[key], obj);
    }

    // Hide all cards initially
    config.forEach(({ selector }) => $(selector).hide());

    // Update each card with flow data
    config.forEach(({ key, selector, fields, fallback }) => {
        let data = flowData[key];
        if (!data && fallback) {
            data = getNestedValue(flowData, fallback);
        }
        if (!data) return;

        const container = $(selector);
        if (!container.length) return;

        const valueEl = container.find(".stats-small__value");
        const percentEl = container.find(".stats-small__percentage");

        const valueText = fields.map(f => data?.[f] ?? "").filter(Boolean).join("/") || "N/A";
        const dateText = data?.dateJs ?? data?.Date ?? flowData.DateJs ?? "";

        if (valueEl.length) valueEl.html(valueText);
        if (percentEl.length) percentEl.html(`<small>Updated: ${dateText}</small>`);
    });

    // Animate cards sequentially
    (function slideNext(index) {
        if (index >= config.length) return;
        const container = $(config[index].selector);
        if (container.length) {
            container.slideDown(() => slideNext(index + 1));
        } else {
            slideNext(index + 1);
        }
    })(0);
}
const SindhFlows = { 
    TodayFlow: null,
    date: [],
    Dates_DD_MM: [],
    Dates_DD_MM_YY: [], 
    Sindh_Accord: [],
    Sindh_Actual: [],
    Sindh_Balochistan_withdrawal: [],
    SindhBaloch_WaterAccord: [],
    SindhBaloch_ActualWD: [],

    GudduBarrage: {
        US: [],
        DS: [],
        WaterAccord: [],
        Storage: [],
        Percent: [],
        TotalPercent: [],
        AccordTotal: [],
        ActualWD: [],
        ActualWDTotal: [],
        RightBank_Level: {
            US: [],
            DS: []
        },
        LeftBank_Level: {
            US: [],
            DS: []
        },
        BegarSindhFeeder: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        DesrtPatFeeder: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        Ghotki: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        Rainee: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        }
    },
    SukkurBarrage: {
        US: [],
        DS: [],
        WaterAccord: [],
        Storage: [],
        Percent: [],
        PercentTotal: [],
        AccordTotal: [],
        ActualWD: [],
        ActualWDTotal: [],
        RightBank_Level: {
            US: [],
            DS: [],
        },
        LeftBank_Level: {
            US: [],
            DS: []
        },
        NWCanal: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        RiceCanal: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        DaduCanal: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        NaraCanal: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        RohriCanal: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        KFEast: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        KFWest: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        }
    },
    KotriBarrage: {
        US: [],
        DS: [],
        WaterAccord: [],
        Storage: [],
        Percent: [],
        //      PercentTotal: [],
        //     AccordTotal: [],
        ActualWD: [],
        //     ActualWDTotal: [],
        RightBank_Level: {
            US: [],
            DS: []
        },
        LeftBank_Level: {
            US: [],
            DS: []
        },
        KalriBegarFeeder: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        AkramWah: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        Pinyari: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        },
        Fuleli: {
            Actual: [],
            WaterAccord: [],
            Percent: [],
            Remarks: []
        }

    },
    Balochistan: {
        BalochistanActual: [],
        GudduActualWD: [],
        GudduBarrage_Accord: [],
        KhirtharRD102: [],
        Manhiti: [],
        PatRD109: [],
        UchDistry: [],
        Kachi:[],
        Sindhwithdrawal: [],
        SukkurActualWD: [],
        SukkurBarrage_Accord: []
    },
    LatestFlows: {
        flowData: null,
        Date: null,
        DateJs: null,

        GudduSummary: {},
        SukkurSummary: {},
        KotriSummary: {},

        GudduCanals: {},
        SukkurCanals: {},
        KotriCanals: {},

        Reservoir: {
            Tarbela: {},
            Mangla: {},
            Kabul: {},
            Marala: {},
            Kalabagh: {},
            Chashma: {},
            Taunsa: {}
        },

        LinkCanals: {
            Thal: {},
            CJLink: {},
            CRB: {},
            DGKhan: {},
            MuzafarGarh: {},
            TPLink: {}
        },

        Tributary: {
            Rasul: {},
            Qadirabad: {},
            Trimmu: {},
            Balloki: {},
            Sidhnai: {},
            Sulemanki: {},
            Islam: {}
        }
    }


};

/* Pak */
const PakFlow = {
    date: [],
    Dates_DD_MM: [],
    Dates_DD_MM_YY: [],

    PakReservoirs: null,
    PakPunjabwithdrawl: null,
    PakTributry: null,

    ReservoirsComparative: null,
    SindhBarragesComparative: null,
       
    Punjabwithdrawl: {
        date: [],
        Dates_DD_MM: [],
        Dates_DD_MM_YY: [],
        CJLink: {
            accord: [],
            flows: []
        },
        CRB: {
            accord: [],
            flows: []
        },
        DGKhan: {
            accord: [],
            flows: []
        },
        MuzafarGarh: {
            accord: [],
            flows: []
        },
        TPLink: {
            accord: [],
            flows: []
        },
        Thal: {
            accord: [],
            flows: []
        }
    },
 
    Tributry: {
        date: [],
        Dates_DD_MM: [],
        Dates_DD_MM_YY: [],
        Mangla: {
            Inflow: [],
            Outflow: [],
            Level: []
        },
        Marala: {
            Inflow: [],
            Outflow: []
        },
        QADIRABAD: {
            Inflow: [],
            Outflow: []
        },
        RASUL: {
            Inflow: [],
            Outflow: []
        },
        SIDHNAI: {
            Inflow: [],
            Outflow: []
        },
        SULEMANKI: {
            Inflow: [],
            Outflow: []
        },
        TRIMMU: {
            Inflow: [],
            Outflow: []
        },
        BALLOKI: {
            Inflow: [],
            Outflow: []
        },
        ISLAM: {
            Inflow: [],
            Outflow: []
        },

    },
  
    Tarbela: {
        Inflow: [],
        Outflow: [],
        Level: []
    },
    Kabul: {
        Discharge: [],
        Level: []
    },
    Kalabagh: {
        Inflow: [],
        Outflow: [],
        Level_US: [],
        Level_DS: []
    },
    Chashma: {
        Inflow: [],
        Outflow: [],
        Storage: [],
        Level_US: [],
        Level_DS: [],
        Withdrawals: [],
    },


    Panjnad: {
        Inflow: [],
        Outflow: [],
        Level_US: [],
        Level_DS: []
    },
    Taunsa: {
        Inflow: [],
        Outflow: [],
        Level_US: [],
        Level_DS: []
    }
};

const SindhCharts = {
    Guddu: (title = "Guddu Barrage", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "U/S", Values: SindhFlows.GudduBarrage.US }, { title: "D/S", Values: SindhFlows.GudduBarrage.DS }, title, "ChartGuddu", type, displayLabels, displayCount),

    Begar: (title = "Begar Sindh Feeder", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.GudduBarrage.BegarSindhFeeder.Actual }, { title: "WaterAccord", Values: SindhFlows.GudduBarrage.BegarSindhFeeder.WaterAccord }, title, "ChartGuddu", type, displayLabels, displayCount),

    Desert: (title = "Desert Pat Feeder", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.GudduBarrage.DesrtPatFeeder.Actual }, { title: "WaterAccord", Values: SindhFlows.GudduBarrage.DesrtPatFeeder.WaterAccord }, title, "ChartGuddu", type, displayLabels, displayCount),

    Ghotki: (title = "Ghotki", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.GudduBarrage.Ghotki.Actual }, { title: "WaterAccord", Values: SindhFlows.GudduBarrage.Ghotki.WaterAccord }, title, "ChartGuddu", type, displayLabels, displayCount),

    GudduBarrageRBLevels: (title = "Guddu Right Bank Levels", type = "bar", displayLabels = true, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "US Level", Values: SindhFlows.GudduBarrage.RightBank_Level.US }, { title: "DS Level", Values: SindhFlows.GudduBarrage.RightBank_Level.DS }, title, "ChartGuddu", type, displayLabels, displayCount),

    GudduBarrageLBLevels: (title = "Guddu Left Bank Levels", type = "bar", displayLabels = true, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "US Level", Values: SindhFlows.GudduBarrage.LeftBank_Level.US }, { title: "DS Level", Values: SindhFlows.GudduBarrage.LeftBank_Level.DS }, title, "ChartGuddu", type, displayLabels, displayCount),

    Sukkur: (title = "Sukkur Barrage", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "U/S", Values: SindhFlows.SukkurBarrage.US }, { title: "D/S", Values: SindhFlows.SukkurBarrage.DS }, title, "ChartSukkur", type, displayLabels, displayCount),

    NWCanal: (title = "North West Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.NWCanal.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.NWCanal.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    RiceCanal: (title = "Rice Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.RiceCanal.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.RiceCanal.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    DaduCanal: (title = "Dadu Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.DaduCanal.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.DaduCanal.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    NaraCanal: (title = "Nara Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.NaraCanal.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.NaraCanal.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    RohriCanal: (title = "Rohri Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.RohriCanal.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.RohriCanal.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    KFEast: (title = "Khairpur Feeder East", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.KFEast.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.KFEast.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    KFWest: (title = "Khairpur Feeder West", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.SukkurBarrage.KFWest.Actual }, { title: "WaterAccord", Values: SindhFlows.SukkurBarrage.KFWest.WaterAccord }, title, "ChartSukkur", type, displayLabels, displayCount),

    Kotri: (title = "Kotri Barrage", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "U/S", Values: SindhFlows.KotriBarrage.US }, { title: "D/S", Values: SindhFlows.KotriBarrage.DS }, title, "ChartKotri", type, displayLabels, displayCount),

    KalriBegarFeeder: (title = "Kalri Begar Feeder", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.KotriBarrage.KalriBegarFeeder.Actual }, { title: "WaterAccord", Values: SindhFlows.KotriBarrage.KalriBegarFeeder.WaterAccord }, title, "ChartKotri", type, displayLabels, displayCount),

    Pinyari: (title = "Pinyari (Old Phuleli)", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.KotriBarrage.Pinyari.Actual }, { title: "WaterAccord", Values: SindhFlows.KotriBarrage.Pinyari.WaterAccord }, title, "ChartKotri", type, displayLabels, displayCount),

    AkramWah: (title = "Akram Wah", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.KotriBarrage.AkramWah.Actual }, { title: "WaterAccord", Values: SindhFlows.KotriBarrage.AkramWah.WaterAccord }, title, "ChartKotri", type, displayLabels, displayCount),

    Fuleli: (title = "Fuleli Canal", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.KotriBarrage.Fuleli.Actual }, { title: "WaterAccord", Values: SindhFlows.KotriBarrage.Fuleli.WaterAccord }, title, "ChartKotri", type, displayLabels, displayCount),

    KotriRBLevels: (title = "Kotri Right Bank Levels", type = "bar", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "US Level", Values: SindhFlows.KotriBarrage.RightBank_Level.US }, { title: "DS Level", Values: SindhFlows.KotriBarrage.RightBank_Level.DS }, title, "ChartKotri", type, displayLabels, displayCount),

    KotriLBLevels: (title = "Kotri Left Bank Levels", type = "bar", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "US Level", Values: SindhFlows.KotriBarrage.LeftBank_Level.US }, { title: "DS Level", Values: SindhFlows.KotriBarrage.LeftBank_Level.DS }, title, "ChartKotri", type, displayLabels, displayCount),

    BalochistanGudduBarrageShare: (title = "Guddu Barrage – Balochistan Share", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.Balochistan.GudduActualWD }, { title: "Water Accord", Values: SindhFlows.Balochistan.GudduBarrage_Accord }, title, "ChartGudduB", type, displayLabels, displayCount),

    PatRD109: (title = "Pat RD109", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Actual", Values: SindhFlows.Balochistan.PatRD109 }, null, title, "ChartGudduB", type, displayLabels, displayCount),

    UchDistry: (title = "Uch Distry", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "UchDistry", Values: SindhFlows.Balochistan.UchDistry }, null, title, "ChartGudduB", type, displayLabels, displayCount),

    Manhiti: (title = "Manhiti", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Manhiti", Values: SindhFlows.Balochistan.Manhiti }, null, title, "ChartGudduB", type, displayLabels, displayCount),

    SukkurB: (title = "Sukkur Barrage – Balochistan Share", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Pat RD 109", Values: SindhFlows.Balochistan.PatRD109 }, { title: "Water Accord", Values: SindhFlows.Balochistan.SukkurBarrage_Accord }, title, "ChartGudduB", type, displayLabels, displayCount),

    Kachi: (title = "Kachi", type = "line", displayLabels = false, displayCount = 60) =>
        LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY, { title: "Kachi", Values: SindhFlows.Balochistan.Kachi }, null, title, "ChartGudduB", type, displayLabels, displayCount)
};



function SindhSetupTabs(strContainer) {
    var ContainerID = strContainer; //
    let Container = $('.' + ContainerID + '-container');
    if (Container) {
        let objFilter = $('#' + ContainerID + '-flters li');
        objFilter.click(function (e) {
            e.preventDefault();
            for (var a = 0; a < objFilter.length; a++) {
                objFilter[a].classList.remove('filter-active');
            }
            this.classList.add('filter-active');

            if (this.getAttribute('data-filter') == ".filter-guddu") {
                SindhCharts.Guddu();
            }
            else if (this.getAttribute('data-filter') == ".filter-Begar") {
                SindhCharts.Begar();
            }
            else if (this.getAttribute('data-filter') == ".filter-Desert") {
                SindhCharts.Desert();
            }
            else if (this.getAttribute('data-filter') == ".filter-Ghotki") {
                SindhCharts.Ghotki();
            }
            else if (this.getAttribute('data-filter') == ".filter-GhotkiRBLevels") {
                SindhCharts.GudduBarrageRBLevels();
            }
            else if (this.getAttribute('data-filter') == ".filter-GhotkiLBLevels") {
                SindhCharts.GudduBarrageLBLevels();
            }
            else if (this.getAttribute('data-filter') == ".filter-sukkur") {
                SindhCharts.Sukkur();
            }
            else if (this.getAttribute('data-filter') == ".filter-nw") {
                SindhCharts.NWCanal();
            }
            else if (this.getAttribute('data-filter') == ".filter-RiceCanal") {
                SindhCharts.RiceCanal();

            }
            else if (this.getAttribute('data-filter') == ".filter-DaduCanal") {
                SindhCharts.DaduCanal();
            }
            else if (this.getAttribute('data-filter') == ".filter-NaraCanal") {
                SindhCharts.NaraCanal();
            }
            else if (this.getAttribute('data-filter') == ".filter-RohriCanal") {
                SindhCharts.RohriCanal();

            }
            else if (this.getAttribute('data-filter') == ".filter-KFEast") {
                SindhCharts.KFEast();
            }
            else if (this.getAttribute('data-filter') == ".filter-KFWest") {
                SindhCharts.KFWest();
            }

            else if (this.getAttribute('data-filter') == ".filter-kotri") {
                SindhCharts.Kotri();
            }
            else if (this.getAttribute('data-filter') == ".filter-kbf") {
                SindhCharts.KalriBegarFeeder();
            }
            else if (this.getAttribute('data-filter') == ".filter-Pinyari") {
                SindhCharts.Pinyari();
            }
            else if (this.getAttribute('data-filter') == ".filter-AkramWah") {
                SindhCharts.AkramWah();
            } else if (this.getAttribute('data-filter') == ".filter-Fuleli") {
                SindhCharts.Fuleli();
            }
            else if (this.getAttribute('data-filter') == ".filter-kotrirbgauges") {
                SindhCharts.KotriRBLevels();
            }
            else if (this.getAttribute('data-filter') == ".filter-kotrilbgauges") {
                SindhCharts.KotriLBLevels();

            }
            else if (this.getAttribute('data-filter') == ".filter-GudduB") {
                SindhCharts.BalochistanGudduBarrageShare();

            }
            else if (this.getAttribute('data-filter') == ".filter-PatRD109") {

                SindhCharts.PatRD109();
            }
            else if (this.getAttribute('data-filter') == ".filter-UchDistry") {
                SindhCharts.UchDistry();

            }
            else if (this.getAttribute('data-filter') == ".filter-Manhiti") {
                SindhCharts.Manhiti();

            } else if (this.getAttribute('data-filter') == ".filter-SukkurB") {
                SindhCharts.SukkurB();

            } else if (this.getAttribute('data-filter') == ".filter-Kachi") {
                SindhCharts.Kachi();
            }

        })

    }
}

async function LoadKotriBarragePage() {
    await RenderSindhFlow();
    await RenderLatestFlow();
    SindhSetupTabs('KotriBarrage');
    // Load and prepare data
    const Flows = SindhFlows.TodayFlow || [];
    if (!Array.isArray(Flows) || Flows.length === 0) {
        console.warn("No flow data available.");
        return;
    }


    SindhCharts.Kotri();

    function LoadFlowTable(FlowData) {
        const datasets = FlowData;
        const getPercentKeys = [
            "GudduBarrage_TotalPercent", "BegarSindhFeeder_Percent", "DesrtPatFeeder_Percent", "Ghotki_Percent",
            "SukkurBarrage_PercentTotal", "NWCanal_Percent", "RiceCanal_Percent", "DaduCanal_Percent",
            "NaraCanal_Percent", "KFEast_Percent", "RohriCanal_Percent", "KFWest_Percent",
            "KotriBarrage_Percent", "KalriBegarFeeder_Percent", "AkramWah_Percent", "Pinyari_Percent", "Fuleli_Percent"
        ];

        const fillTemplate = (template, data) => {
            return template.replace(/{(\w+)}/g, (_, key) => {
                const val = data[key];
                return getPercentKeys.includes(key) ? getPercent(val) : (val ?? "");
            });
        };


        const tmpKotri = `
        <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
        <td>{KotriBarrage_upstream}</td><td>{KotriBarrage_downstream}</td><td>{KotriBarrage_ActualWD}</td><td>{KotriBarrage_WaterAccord}</td><td>{KotriBarrage_Percent}</td>
        <td>{KalriBegarFeeder}</td><td>{KalriBegarFeeder_WaterAccord}</td><td>{KalriBegarFeeder_Percent}</td>
        <td>{AkramWah}</td><td>{AkramWah_WaterAccord}</td><td>{AkramWah_Percent}</td>
        <td>{Pinyari}</td><td>{Pinyari_WaterAccord}</td><td>{Pinyari_Percent}</td>
        <td>{Fuleli}</td><td>{Fuleli_WaterAccord}</td><td>{Fuleli_Percent}</td></tr>
    `;


        const tmpMonth = `<tr><th colspan="{span}" style="text-align:left">{month}</th></tr>`;

        let kotrids = "";
        for (let i = 0; i < datasets.length; i++) {
            const jdata = datasets[i];
            let dt;
            try {
                dt = new Date(jdata["dated"]);
            } catch (e) {
                continue;
            }
            const formattedDate = moment(dt).format('DD-MM-YYYY') || dt.toLocaleDateString('en-GB').replace(/\//g, '-');
            jdata["datejs"] = formattedDate;
            jdata["sr"] = i + 1;

            if (dt.getDate() === 1) {
                const monthLabel = jdata["Monthjs"];
                kotrids += tmpMonth.replace("{span}", "19").replace("{month}", monthLabel);

            }
            kotrids += fillTemplate(tmpKotri, jdata);

        }

        $("#tblKotri").html(kotrids);
    }
    LoadFlowTable(SindhFlows.TodayFlow);



}
async function LoadSukkurBarragePage() {
    await RenderSindhFlow();
    await RenderLatestFlow();
    SindhSetupTabs('SukkurBarrage');
    // Load and prepare data
    const Flows = SindhFlows.TodayFlow || [];
    if (!Array.isArray(Flows) || Flows.length === 0) {
        console.warn("No flow data available.");
        return;
    }

   
    SindhCharts.Sukkur();
    
    function LoadFlowTable(FlowData) {
        const datasets = FlowData;
        const getPercentKeys = [
            "GudduBarrage_TotalPercent", "BegarSindhFeeder_Percent", "DesrtPatFeeder_Percent", "Ghotki_Percent",
            "SukkurBarrage_PercentTotal", "NWCanal_Percent", "RiceCanal_Percent", "DaduCanal_Percent",
            "NaraCanal_Percent", "KFEast_Percent", "RohriCanal_Percent", "KFWest_Percent",
            "KotriBarrage_Percent", "KalriBegarFeeder_Percent", "AkramWah_Percent", "Pinyari_Percent", "Fuleli_Percent"
        ];

        const fillTemplate = (template, data) => {
            return template.replace(/{(\w+)}/g, (_, key) => {
                const val = data[key];
                return getPercentKeys.includes(key) ? getPercent(val) : (val ?? "");
            });
        };
 

        const tmpSukkur = `
      <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
      <td>{SukkurBarrage_upstream}</td><td>{SukkurBarrage_downstream}</td><td>{SukkurBarrage_ActualWDTotal}</td><td>{SukkurBarrage_WaterAccord}</td><td>{SukkurBarrage_PercentTotal}</td>
      <td>{NWCanal}</td><td>{NWCanal_WaterAccord}</td><td>{NWCanal_Percent}</td>
      <td>{RiceCanal}</td><td>{RiceCanal_WaterAccord}</td><td>{RiceCanal_Percent}</td>
      <td>{DaduCanal}</td><td>{DaduCanal_WaterAccord}</td><td>{DaduCanal_Percent}</td>
      <td>{NaraCanal}</td><td>{NaraCanal_WaterAccord}</td><td>{NaraCanal_Percent}</td>
      <td>{KFEast}</td><td>{KFEast_WaterAccord}</td><td>{KFEast_Percent}</td>
      <td>{RohriCanal}</td><td>{RohriCanal_WaterAccord}</td><td>{RohriCanal_Percent}</td>
      <td>{KFWest}</td><td>{KFWest_WaterAccord}</td><td>{KFWest_Percent}</td></tr>
  `;
   

        const tmpMonth = `<tr><th colspan="{span}" style="text-align:left">{month}</th></tr>`;

        let   sukkurds = "" ; 
        for (let i = 0; i < datasets.length; i++) {
            const jdata = datasets[i]; 
            let dt;
            try {
                dt = new Date(jdata["dated"]);
            } catch (e) {
                continue;
            } 
            const formattedDate = moment(dt).format('DD-MM-YYYY') || dt.toLocaleDateString('en-GB').replace(/\//g, '-');
            jdata["datejs"] = formattedDate;
            jdata["sr"] = i + 1; 

            if (dt.getDate() === 1) {
                const monthLabel = jdata["Monthjs"];
                 sukkurds += tmpMonth.replace("{span}", "28").replace("{month}", monthLabel);
               
            } 
            sukkurds += fillTemplate(tmpSukkur, jdata);   
        } 
        $("#tblSukkur").html(sukkurds); 
    }
    LoadFlowTable(SindhFlows.TodayFlow);

     
    
}
async function LoadGudduBarragePage() {
    await RenderSindhFlow();
    await RenderLatestFlow();
    SindhSetupTabs('GudduBarrage');
    SindhSetupTabs('Balochistan');
    // Load and prepare data
    const Flows = SindhFlows.TodayFlow || [];
    if (!Array.isArray(Flows) || Flows.length === 0) {
        console.warn("No flow data available.");
        return;
    }
    SindhCharts.Guddu();
    SindhCharts.BalochistanGudduBarrageShare();
    function LoadFlowTable(FlowData) {
        const datasets = FlowData;
        const getPercentKeys = [
            "GudduBarrage_TotalPercent", "BegarSindhFeeder_Percent", "DesrtPatFeeder_Percent", "Ghotki_Percent",
            "SukkurBarrage_PercentTotal", "NWCanal_Percent", "RiceCanal_Percent", "DaduCanal_Percent",
            "NaraCanal_Percent", "KFEast_Percent", "RohriCanal_Percent", "KFWest_Percent",
            "KotriBarrage_Percent", "KalriBegarFeeder_Percent", "AkramWah_Percent", "Pinyari_Percent", "Fuleli_Percent"
        ];

        const fillTemplate = (template, data) => {
            return template.replace(/{(\w+)}/g, (_, key) => {
                const val = data[key];
                return getPercentKeys.includes(key) ? getPercent(val) : (val ?? "");
            });
        };

        const tmpGuddu = `
     <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
     <td>{GudduBarrage_upstream}</td><td>{GudduBarrage_downstream}</td><td>{GudduBarrage_ActualWDTotal}</td><td>{GudduBarrage_WaterAccord}</td><td>{GudduBarrage_TotalPercent}</td>
     <td>{BegarSindhFeeder}</td><td>{BegarSindhFeeder_WaterAccord}</td><td>{BegarSindhFeeder_Percent}</td>
     <td>{DesrtPatFeeder}</td><td>{DesrtPatFeeder_WaterAccord}</td><td>{DesrtPatFeeder_Percent}</td>
     <td>{Ghotki}</td><td>{Ghotki_WaterAccord}</td><td>{Ghotki_Percent}</td></tr>
 `;
  

        const tmpBalochistan = `<tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
     <td>{GudduActualWD}</td><td>{GudduBarrage_Accord}</td><td>{GudduPercentage}</td>
     <td>{PatRD109}</td><td>{UchDistry}</td><td>{Manhiti}</td><td>{GudduActualWD}</td>
     <td>{SukkurActualWD}</td><td>{SukkurBarrage_Accord}</td><td>{SukkurPercentage}</td>
     <td>{Kachi}</td><td>{BalochistanActual}</td></tr>`;


        const tmpMonth = `<tr><th colspan="{span}" style="text-align:left">{month}</th></tr>`;

        let gudduds = "",   balochistands = "";


        for (let i = 0; i < datasets.length; i++) {
            const jdata = datasets[i];
            const balo = jdata.balochistan || {}; 
            let dt;
            try {
                dt = new Date(jdata["dated"]);
            } catch (e) {
                continue;
            } 
            const formattedDate = moment(dt).format('DD-MM-YYYY') || dt.toLocaleDateString('en-GB').replace(/\//g, '-');
            jdata["datejs"] = formattedDate;
            jdata["sr"] = i + 1; 
            balo["datejs"] = formattedDate;
            balo["sr"] = i + 1; 
            if (dt.getDate() === 1) {
                const monthLabel = jdata["Monthjs"];
                gudduds += tmpMonth.replace("{span}", "16").replace("{month}", monthLabel);
                balochistands += tmpMonth.replace("{span}", "14").replace("{month}", monthLabel);

            }

            gudduds += fillTemplate(tmpGuddu, jdata); 

            balochistands += fillTemplate(tmpBalochistan, balo);

        }

        $("#tblGhotki").html(gudduds); 
        $("#tblBalochistan").html(balochistands);

    }
    LoadFlowTable(SindhFlows.TodayFlow);
}
async function LoadSindhFlowsPage() {
    await RenderSindhFlow();
    await RenderLatestFlow(); 
    LoadBackgroundCharts(9); 
    UpdateFlowStats(SindhFlows.LatestFlows); 
    
  
    function ShowBanner(data) {
        let chartid = 'myChart';
        const updateCell = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = value ?? "";
        };

        // Set date headers
        updateCell("tendaily", data.datetendaily);
        updateCell("datajs", data.datejs);

        // Baluchistan
        const balochistan = data.balochistan || {};
        updateCell("PatRD93", balochistan.GudduActualWD);
        updateCell("PatRD93_WaterAccord", balochistan.GudduBarrage_Accord);
        updateCell("Khirthar", balochistan.SukkurActualWD);
        updateCell("Khirthar_WaterAccord", balochistan.SukkurBarrage_Accord);

        // Barrage totals
        updateCell("guddu_wateractual", data.GudduBarrage_ActualWDTotal);
        updateCell("guddu_wateraccord", data.GudduBarrage_AccordTotal);
        updateCell("guddu_Percent", getPercent(data.GudduBarrage_TotalPercent));
        updateCell("guddu_Remarks", "Balochistan share included");

        updateCell("sukkur_wateractual", data.SukkurBarrage_ActualWDTotal);
        updateCell("sukkur_wateraccord", data.SukkurBarrage_WaterAccord);
        updateCell("sukkur_Percent", getPercent(data.SukkurBarrage_PercentTotal));
        updateCell("sukkur_Remarks", "Balochistan share included");

        updateCell("kotri_wateractual", data.KotriBarrage_ActualWD);
        updateCell("kotri_wateraccord", data.KotriBarrage_WaterAccord);
        updateCell("kotri_Percent", getPercent(data.KotriBarrage_Percent));
        updateCell("kotri_Remarks", "");

        updateCell("SB_wateractual", data.SindhBaloch_ActualWD);
        updateCell("SB_wateraccord", data.SindhBaloch_WaterAccord);
        updateCell("SB_Percent", getPercent(data.SindhBaloch_Percent));
        updateCell("SB_Remarks", "");

        updateCell("S_wateractual", data.Sindh_Actual);
        updateCell("S_wateraccord", data.Sindh_Accord);
        updateCell("S_Percent", getPercent(data.Sindh_Percent));
        updateCell("S_Remarks", `Excluding Baluchistan (${data.Sindh_Balochistan_withdrawal}) Actual`);

        updateCell("Rainee", data.Rainee);
        updateCell("Rainee_WaterAccord", data.Rainee_WaterAccord);

        // Canal keys
        const canalKeys = [
            "Ghotki", "BegarSindhFeeder", "DesrtPatFeeder", "NaraCanal", "KFEast", "RohriCanal", "KFWest",
            "NWCanal", "RiceCanal", "DaduCanal", "AkramWah", "Fuleli", "Pinyari", "KalriBegarFeeder"
        ];

        const dayflow = [], wateraccord = [];

        canalKeys.forEach(key => {
            updateCell(key, data[key]);
            updateCell(`${key}_WaterAccord`, data[`${key}_WaterAccord`]);
            updateCell(`${key}_Percent`, getPercent(data[`${key}_Percent`]));
            updateCell(`${key}_Remarks`, data[`${key}_Remarks`]);

            dayflow.push(data[key]);
            wateraccord.push(data[`${key}_WaterAccord`]);
        });

        // Highlight rows based on remarks
        $('#tblTable tr').removeClass("table-primary table-danger");
        $('#tblTable td').each(function () {
            const text = $(this).text().trim();
            if (text === "Highest Surplus") {
                $(this).parent().addClass("table-primary");
            } else if (text === "Highest Shortfall") {
                $(this).parent().addClass("table-danger");
            }
        });

        // Stats blocks
        const updateStats = (id, upstream, downstream, percent, accord, actual) => {
            $(`#${id} .stats-small__value`).html(`${upstream}/${downstream}`);
            $(`#${id} .stats-small__percentage`).html(getPercent(percent));
            $(`#${id} .wateraccord`).html(accord);
            $(`#${id} .wateractual`).html(actual);

            const el = $(`#${id} .stats-small__percentage`);
            el.removeClass("stats-small__percentage--increase stats-small__percentage--decrease")
                .addClass(percent > 0 ? "stats-small__percentage--increase" : "stats-small__percentage--decrease");
        };

        try {
            updateStats("Guddu", data.GudduBarrage_upstream, data.GudduBarrage_downstream, data.GudduBarrage_TotalPercent, data.GudduBarrage_WaterAccord, data.GudduBarrage_ActualWD);
            updateStats("Sukkur", data.SukkurBarrage_upstream, data.SukkurBarrage_downstream, data.SukkurBarrage_PercentTotal, data.SukkurBarrage_WaterAccord, data.SukkurBarrage_ActualWD);
            updateStats("Kotri", data.KotriBarrage_upstream, data.KotriBarrage_downstream, data.KotriBarrage_Percent, data.KotriBarrage_WaterAccord, data.KotriBarrage_ActualWD);
        } catch (e) {
            console.error("Stats block error:", e);
        }

     
        
        const chartData = {
             
            labels: ['Ghotki Feeder', 'Begari Sindh Feeder', 'Desert Pat Feeder', "Nara Canal", "K F East", "Rohri Canal", "K F West", 'North West Canal', 'Rice Canal', 'Dadu Canal', "Akram Wah", "New Fuleli", "Old Fuleli", "Kalri Baghar Feeder"],
            datasets: [
                {
                    label: 'Actual',
                    data: dayflow,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)', 
                    borderWidth: 1
                },
                {
                    label: 'Water Accords',
                    data: wateraccord,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }
            ]
        };
        CreateChart(chartData.labels, chartData.datasets, "Sindh Canal Daily Flow", "Source : Director Regulation", "myChart", "bar",true);
         
    }

    SindhSetupTabs('GudduBarrage');
    SindhSetupTabs('SukkurBarrage');
    SindhSetupTabs('KotriBarrage');
    SindhSetupTabs('Balochistan');
   
    // Load and prepare data
    const Flows = SindhFlows.TodayFlow || [];
    if (!Array.isArray(Flows) || Flows.length === 0) {
        console.warn("No flow data available.");
        return;
    }

    const chartElement = document.getElementById("myChart");

    if (chartElement) {
        ShowBanner(Flows[Flows.length - 1]);
    } else {
        
    }


    

     
    function LineAreaChart(id, dated, obj) {
        const canvasEl = document.querySelector('canvas.blog-overview-stats-small-' + id);
        if (!canvasEl) {
            console.warn(`Canvas element not found for ID: ${id}`);
            return;
        }

        const ctx = canvasEl.getContext('2d');
        if (!ctx) {
            console.warn(`Unable to get 2D context for canvas ID: ${id}`);
            return;
        }


        var data1 = {
            labels: dated,
            datasets: [{
                label: 'Today',
                fill: 'start',
                data: obj.data,
                backgroundColor: obj.backgroundColor,
                borderColor: obj.borderColor,
                borderWidth: 1.5,
                pointRadius: 0,
                lineTension: 0.4
            },
            {
                label: 'Today',
                fill: 'start',
                data: obj.WaterAccord,
                backgroundColor: obj.backgroundColor2,
                borderColor: obj.borderColor2,
                borderWidth: 1.5,
                pointRadius: 0,
                lineTension: 0.4
            }
            ]
        };
        var fulldata = {
            type: 'line',
            data: data1,
            options: {
                maintainAspectRatio: true,
                responsive: true,
                plugins: {
                    legend: {
                        display: false // hides dataset labels
                    },
                    tooltip: {
                        enabled: false // disables hover labels
                    },
                    title: {
                        display: false // hides chart title if present
                    },
                    datalabels: {
                        display: false // if using chartjs-plugin-datalabels
                    }
                },
                elements: {
                    point: {
                        radius: 0
                    }
                },
                scales: {
                    x: {
                        display: false, // hides x-axis labels
                        ticks: { display: false },
                        grid: { display: false }
                    },
                    y: {
                        display: false, // hides y-axis labels
                        ticks: { display: false },
                        grid: { display: false }
                    }
                }


            },

        };


        if (!objCharts[id]) {
            objCharts[id] = new Chart(ctx, fulldata);
        } else {
            objCharts[id].data = data1;
            objCharts[id].update();
        }

    }  
    const p_barrage = {
        dated: [],
        guddu: {
            backgroundColor: 'rgba(0, 184, 216, 0.1)',
            borderColor: 'rgb(0, 184, 216)',
            borderColor2: 'rgba(75, 192, 192,1)',
            backgroundColor2: 'rgba(75, 192, 192,0.2)',
            data: [],
            WaterAccord: [],
        
        },
        sukkur: {
            backgroundColor: 'rgba(23,198,113,0.1)',
            borderColor: 'rgb(23,198,113)',
            borderColor2: 'rgba(75, 192, 192,1)',
            backgroundColor2: 'rgba(75, 192, 192,0.2)',
            data: [],
            WaterAccord: [],
     
        },
        kotri: {
            backgroundColor: 'rgba(255,180,0,0.1)',
            borderColor: 'rgb(255,180,0)',
            borderColor2: 'rgba(75, 192, 192,1)',
            backgroundColor2: 'rgba(75, 192, 192,0.2)',
            data: [],
            WaterAccord: [],
     
        }
    };

    // Initial chart data population
    Flows.forEach(ds => {
        p_barrage.dated.push(ds.datejs || ds.dated); 
        p_barrage.guddu.data.push(ds["GudduBarrage_ActualWDTotal"] || 0);
        p_barrage.guddu.WaterAccord.push(ds["GudduBarrage_AccordTotal"] || 0);
     
        p_barrage.sukkur.data.push(ds["SukkurBarrage_ActualWDTotal"] || 0);
        p_barrage.sukkur.WaterAccord.push(ds["SukkurBarrage_WaterAccord"] || 0);
 
        p_barrage.kotri.data.push(ds["KotriBarrage_ActualWD"] || 0);
        p_barrage.kotri.WaterAccord.push(ds["KotriBarrage_WaterAccord"] || 0);
     });
   
    // Render initial charts
    LineAreaChart("guddu", p_barrage.dated, p_barrage.guddu);
    LineAreaChart("sukkur", p_barrage.dated, p_barrage.sukkur);
    LineAreaChart("kotri", p_barrage.dated, p_barrage.kotri);
     
    const optionsHtml = Flows.map((ds, index) => {
        const selected = index === Flows.length - 1 ? " selected" : "";
        return `<option value="${index}"${selected}>${ds.datejs}</option>`;
    }).join(""); 
    $("#dtSelect").html(optionsHtml); 
    $("#dtSelect").on("change", function (e) {
        const selectedIndex = parseInt(this.value);
        if (!Number.isInteger(selectedIndex) || selectedIndex < 0 || selectedIndex >= Flows.length) return;
        ShowBanner(SindhFlows.TodayFlow[selectedIndex]);
    });


    SindhCharts.Guddu();
    SindhCharts.Sukkur();   
    SindhCharts.Kotri();
    SindhCharts.BalochistanGudduBarrageShare(); 
         
    function LoadFlowTable(FlowData) {
        const datasets = FlowData; 
        const getPercentKeys = [
            "GudduBarrage_TotalPercent", "BegarSindhFeeder_Percent", "DesrtPatFeeder_Percent", "Ghotki_Percent",
            "SukkurBarrage_PercentTotal", "NWCanal_Percent", "RiceCanal_Percent", "DaduCanal_Percent",
            "NaraCanal_Percent", "KFEast_Percent", "RohriCanal_Percent", "KFWest_Percent",
            "KotriBarrage_Percent", "KalriBegarFeeder_Percent", "AkramWah_Percent", "Pinyari_Percent", "Fuleli_Percent"
        ];

        const fillTemplate = (template, data) => {
            return template.replace(/{(\w+)}/g, (_, key) => {
                const val = data[key];
                return getPercentKeys.includes(key) ? getPercent(val) : (val ?? "");
            });
        };

        const tmpGuddu = `
        <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
        <td>{GudduBarrage_upstream}</td><td>{GudduBarrage_downstream}</td><td>{GudduBarrage_ActualWDTotal}</td><td>{GudduBarrage_WaterAccord}</td><td>{GudduBarrage_TotalPercent}</td>
        <td>{BegarSindhFeeder}</td><td>{BegarSindhFeeder_WaterAccord}</td><td>{BegarSindhFeeder_Percent}</td>
        <td>{DesrtPatFeeder}</td><td>{DesrtPatFeeder_WaterAccord}</td><td>{DesrtPatFeeder_Percent}</td>
        <td>{Ghotki}</td><td>{Ghotki_WaterAccord}</td><td>{Ghotki_Percent}</td></tr>
    `;

        const tmpSukkur = `
        <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
        <td>{SukkurBarrage_upstream}</td><td>{SukkurBarrage_downstream}</td><td>{SukkurBarrage_ActualWDTotal}</td><td>{SukkurBarrage_WaterAccord}</td><td>{SukkurBarrage_PercentTotal}</td>
        <td>{NWCanal}</td><td>{NWCanal_WaterAccord}</td><td>{NWCanal_Percent}</td>
        <td>{RiceCanal}</td><td>{RiceCanal_WaterAccord}</td><td>{RiceCanal_Percent}</td>
        <td>{DaduCanal}</td><td>{DaduCanal_WaterAccord}</td><td>{DaduCanal_Percent}</td>
        <td>{NaraCanal}</td><td>{NaraCanal_WaterAccord}</td><td>{NaraCanal_Percent}</td>
        <td>{KFEast}</td><td>{KFEast_WaterAccord}</td><td>{KFEast_Percent}</td>
        <td>{RohriCanal}</td><td>{RohriCanal_WaterAccord}</td><td>{RohriCanal_Percent}</td>
        <td>{KFWest}</td><td>{KFWest_WaterAccord}</td><td>{KFWest_Percent}</td></tr>
    `;

        const tmpKotri = `
        <tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
        <td>{KotriBarrage_upstream}</td><td>{KotriBarrage_downstream}</td><td>{KotriBarrage_ActualWD}</td><td>{KotriBarrage_WaterAccord}</td><td>{KotriBarrage_Percent}</td>
        <td>{KalriBegarFeeder}</td><td>{KalriBegarFeeder_WaterAccord}</td><td>{KalriBegarFeeder_Percent}</td>
        <td>{AkramWah}</td><td>{AkramWah_WaterAccord}</td><td>{AkramWah_Percent}</td>
        <td>{Pinyari}</td><td>{Pinyari_WaterAccord}</td><td>{Pinyari_Percent}</td>
        <td>{Fuleli}</td><td>{Fuleli_WaterAccord}</td><td>{Fuleli_Percent}</td></tr>
    `;


        const tmpBalochistan = `<tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>
        <td>{GudduActualWD}</td><td>{GudduBarrage_Accord}</td><td>{GudduPercentage}</td>
        <td>{PatRD109}</td><td>{UchDistry}</td><td>{Manhiti}</td><td>{GudduActualWD}</td>
        <td>{SukkurActualWD}</td><td>{SukkurBarrage_Accord}</td><td>{SukkurPercentage}</td>
        <td>{Kachi}</td><td>{BalochistanActual}</td></tr>`;


        const tmpMonth = `<tr><th colspan="{span}" style="text-align:left">{month}</th></tr>`;

        let gudduds = "", sukkurds = "", kotrids = "", balochistands = "";


        for (let i = 0; i < datasets.length; i++) {
            const jdata = datasets[i];
            const balo = jdata.balochistan || {};


            let dt;
            try {
                dt = new Date(jdata["dated"]);
            } catch (e) {
                continue;
            }

            const formattedDate = moment(dt).format('DD-MM-YYYY') || dt.toLocaleDateString('en-GB').replace(/\//g, '-');
            jdata["datejs"] = formattedDate;
            jdata["sr"] = i + 1;

            balo["datejs"] = formattedDate;
            balo["sr"] = i + 1;


            if (dt.getDate() === 1) {
                const monthLabel = jdata["Monthjs"];
                gudduds += tmpMonth.replace("{span}", "16").replace("{month}", monthLabel);
                sukkurds += tmpMonth.replace("{span}", "28").replace("{month}", monthLabel);
                kotrids += tmpMonth.replace("{span}", "19").replace("{month}", monthLabel);
                balochistands += tmpMonth.replace("{span}", "14").replace("{month}", monthLabel);

            }

            gudduds += fillTemplate(tmpGuddu, jdata);
            sukkurds += fillTemplate(tmpSukkur, jdata);
            kotrids += fillTemplate(tmpKotri, jdata);

            balochistands += fillTemplate(tmpBalochistan, balo);

        }

        $("#tblGhotki").html(gudduds);
        $("#tblSukkur").html(sukkurds);
        $("#tblKotri").html(kotrids);
        $("#tblBalochistan").html(balochistands);

    } 
    LoadFlowTable(SindhFlows.TodayFlow);
  
}
 
 
async function LoadIndexPage(ChartID,btnGudduID,btnSukkurID,btnKotriID) { 
     
    const gudduData = JSON.parse(await loadFlow("https://api.hicsindh.pk/public/Flows/gudduflows"));
    const sukkurData = JSON.parse(await loadFlow("https://api.hicsindh.pk/public/Flows/sukkurflows"));
    const kotriData = JSON.parse(await loadFlow("https://api.hicsindh.pk/public/Flows/kotriflows"));
    const formatDate = d => {
        const date = new Date(d);
        return `${String(date.getDate()).padStart(2, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${date.getFullYear()}`;
    }; 
    const flows = {
        [btnGudduID]: {
            title: gudduData.Title,
            chart: ChartID,
            dates: gudduData.FlowsCollection.map(e => formatDate(e.Dated)   ),
            upstream: gudduData.FlowsCollection.map(e => e.Upstream),
            downstream: gudduData.FlowsCollection.map(e => e.Downstream)
        },
        [btnSukkurID]: {
            title: sukkurData.Title,
            chart: ChartID,
            dates: sukkurData.FlowsCollection.map(e => formatDate(e.Dated)),
            upstream: sukkurData.FlowsCollection.map(e => e.Upstream),
            downstream: sukkurData.FlowsCollection.map(e => e.Downstream)
        },
        [btnKotriID]: {
            title: kotriData.Title,
            chart: ChartID,
            dates: kotriData.FlowsCollection.map(e => formatDate(e.Dated)),
            upstream: kotriData.FlowsCollection.map(e => e.Upstream),
            downstream: kotriData.FlowsCollection.map(e => e.Downstream)
        }
    };

    for (let btnId in flows) {
        $("#" + btnId).click(function () {
            const flow = flows[btnId];
            const Series1 = {
                title: flow.title + " D/S",
                Values: flow.downstream
            };

            const Series2 = flow.upstream != null ? {
                title: flow.title + " U/S",
                Values: flow.upstream
            } : null;

            LoadCanalFlowChart(flow.dates, Series1, Series2, flow.title,
                flow.chart, "line", false, 0);
                 
           
        });
    }

    $("#" + btnGudduID).click();

  

    function fillTable(data, chartId) {
        const updateCell = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = value ?? "";
        };

        // Date header
        updateCell("datajs", data.datejs);

        // Baluchistan
        const balochistan = data.balochistan || {}; 
        updateCell("PatRD93", balochistan.PatRD109);
        updateCell("PatRD93_WaterAccord", balochistan.GudduBarrage_Accord);
        updateCell("Khirthar", balochistan.KhirtharRD102);
        updateCell("Khirthar_WaterAccord", balochistan.SukkurBarrage_Accord);
        //updateCell("Khirthar_Percent", balochistan.SukkurPercentage + "%");

        // Canal keys
        const canalKeys = [
            "Rainee", "Ghotki", "BegarSindhFeeder", "DesrtPatFeeder",
            "NaraCanal", "KFEast", "RohriCanal", "KFWest",
            "NWCanal", "RiceCanal", "DaduCanal", "AkramWah",
            "Pinyari", "Fuleli", "KalriBegarFeeder"
        ];

        canalKeys.forEach(key => {
            updateCell(key, data[key]);
            updateCell(`${key}_WaterAccord`, data[`${key}_WaterAccord`]);
            updateCell(`${key}_Percent`, data[`${key}_Percent`]);
            updateCell(`${key}_Remarks`, data[`${key}_Remarks`]);
        });

        // Barrage totals
        updateCell("guddu_wateractual", data.GudduBarrage_ActualWDTotal);
        updateCell("guddu_wateraccord", data.GudduBarrage_AccordTotal);
        updateCell("guddu_Percent", data.GudduBarrage_TotalPercent + "%");
        updateCell("guddu_Remarks", "Balochistan share included");

        updateCell("sukkur_wateractual", data.SukkurBarrage_ActualWDTotal);
        updateCell("sukkur_wateraccord", data.SukkurBarrage_WaterAccord);
        updateCell("sukkur_Percent", data.SukkurBarrage_PercentTotal + "%");
        updateCell("sukkur_Remarks", "Balochistan share included");

        updateCell("kotri_wateractual", data.KotriBarrage_ActualWD);
        updateCell("kotri_wateraccord", data.KotriBarrage_WaterAccord);
        updateCell("kotri_Percent", data.KotriBarrage_Percent + "%");
        updateCell("kotri_Remarks", "");

        updateCell("SB_wateractual", data.SindhBaloch_ActualWD);
        updateCell("SB_wateraccord", data.SindhBaloch_WaterAccord);
        updateCell("SB_Percent", data.SindhBaloch_Percent + "%");
        updateCell("SB_Remarks", "");

        updateCell("S_wateractual", data.Sindh_Actual);
        updateCell("S_wateraccord", data.Sindh_Accord );
        updateCell("S_Percent", data.Sindh_Percent + "%");
        updateCell("S_Remarks", `Excluding Baluchistan (${data.Sindh_Balochistan_withdrawal}) Actual`);







        const canals = [
            { key: "Ghotki", label: "Ghotki Feeder" },
            { key: "BegarSindhFeeder", label: "Begari Sindh Feeder" },
            { key: "DesrtPatFeeder", label: "Desert Pat Feeder" },
            { key: "NaraCanal", label: "Nara Canal" },
            { key: "KFEast", label: "K F East" },
            { key: "RohriCanal", label: "Rohri Canal" },
            { key: "KFWest", label: "K F West" },
            { key: "NWCanal", label: "North West Canal" },
            { key: "RiceCanal", label: "Rice Canal" },
            { key: "DaduCanal", label: "Dadu Canal" },
            { key: "AkramWah", label: "Akram Wah" },
            { key: "Fuleli", label: "New Fuleli" },
            { key: "Pinyari", label: "Old Fuleli" },
            { key: "KalriBegarFeeder", label: "Kalri Baghar Feeder" }
        ];

        const labels = canals.map(c => c.label);
        const dayflow = canals.map(c => data[c.key] ?? 0);
        const wateraccord = canals.map(c => data[`${c.key}_WaterAccord`] ?? 0);

        const chartData = {
            labels,
            datasets: [
                {
                    label: "Actual",
                    data: dayflow,
                    backgroundColor: "rgba(54, 162, 235, 0.2)",
                    borderColor: "rgba(54, 162, 235, 1)",
                    borderWidth: 1
                },
                {
                    label: "Water Accords",
                    data: wateraccord,
                    backgroundColor: "rgba(255, 99, 132, 0.2)",
                    borderColor: "rgba(255, 99, 132, 1)",
                    borderWidth: 1
                }
            ]
        };

        CreateChart(chartData.labels, chartData.datasets, "Sindh Canal Daily Flow", "Source : Director Regulation", chartId, "bar", true);

    }
    let data1 =  await loadFlow("https://api.hicsindh.pk/public/Flows/todayflow") ;
    if (data1) fillTable(data1,"myChart");
   
 

}
async function RenderSindhFlow() {
    SindhFlows.TodayFlow = await loadFlow("https://api.hicsindh.pk/public/Flows/todayflow/1");
    if (!Array.isArray(SindhFlows.TodayFlow) || SindhFlows.TodayFlow.length === 0) {
        console.warn("SindhFlows.TodayFlow is empty or invalid.");
        return;
    }

    const mapFlowData = (key) => SindhFlows.TodayFlow.map(item => item[key]);
    const mapBalochFlowData = (key) => SindhFlows.TodayFlow.map(item => item.balochistan?.[key] ?? null);
    
    // Date formats
    SindhFlows.Dates_DD_MM = SindhFlows.TodayFlow.map(item => moment(item.dated).format("DD-MMM"));
    SindhFlows.Dates_DD_MM_YY = SindhFlows.TodayFlow.map(item => moment(item.dated).format("DD-MMM-YY"));
    SindhFlows.date = SindhFlows.TodayFlow.map(item => new Date(item.dated));

    // Sindh summary
    SindhFlows.Sindh_Actual = mapFlowData('Sindh_Actual');
    SindhFlows.Sindh_Accord = mapFlowData('Sindh_Accord');
    SindhFlows.Sindh_Balochistan_withdrawal = mapFlowData('Sindh_Balochistan_withdrawal');
    SindhFlows.SindhBaloch_WaterAccord = mapFlowData('SindhBaloch_WaterAccord');
    SindhFlows.SindhBaloch_ActualWD = mapFlowData('SindhBaloch_ActualWD');

    // Helper for canals
    const mapCanals = (barrage, canalMap) => {
        Object.entries(canalMap).forEach(([jsonKey, targetKey]) => {
            SindhFlows[barrage][targetKey] = {
                Actual: mapFlowData(jsonKey),
                WaterAccord: mapFlowData(`${jsonKey}_WaterAccord`),
                Percent: mapFlowData(`${jsonKey}_Percent`),
                Remarks: mapFlowData(`${jsonKey}_Remarks`)
            };
        });
    };

    // Guddu Barrage
    SindhFlows.GudduBarrage.US = mapFlowData('GudduBarrage_upstream');
    SindhFlows.GudduBarrage.DS = mapFlowData('GudduBarrage_downstream');
    SindhFlows.GudduBarrage.WaterAccord = mapFlowData('GudduBarrage_WaterAccord');
    SindhFlows.GudduBarrage.Storage = mapFlowData('GudduBarrage_Storage');
    SindhFlows.GudduBarrage.Percent = mapFlowData('GudduBarrage_Percent');
    SindhFlows.GudduBarrage.TotalPercent = mapFlowData('GudduBarrage_TotalPercent');
    SindhFlows.GudduBarrage.AccordTotal = mapFlowData('GudduBarrage_AccordTotal');
    SindhFlows.GudduBarrage.ActualWD = mapFlowData('GudduBarrage_ActualWD');
    SindhFlows.GudduBarrage.ActualWDTotal = mapFlowData('GudduBarrage_ActualWDTotal');
    SindhFlows.GudduBarrage.RightBank_Level.US = mapFlowData('GudduBarrage_Level_RightBank_Upstream');
    SindhFlows.GudduBarrage.RightBank_Level.DS = mapFlowData('GudduBarrage_Level_RightBank_Downstream');
    SindhFlows.GudduBarrage.LeftBank_Level.US = mapFlowData('GudduBarrage_Level_LeftBank_Upstream');
    SindhFlows.GudduBarrage.LeftBank_Level.DS = mapFlowData('GudduBarrage_Level_LeftBank_Downstream');

    mapCanals('GudduBarrage', {
        BegarSindhFeeder: 'BegarSindhFeeder',
        DesrtPatFeeder: 'DesrtPatFeeder',
        Ghotki: 'Ghotki',
        Rainee: 'Rainee'
    });

    // Sukkur Barrage
    SindhFlows.SukkurBarrage.US = mapFlowData('SukkurBarrage_upstream');
    SindhFlows.SukkurBarrage.DS = mapFlowData('SukkurBarrage_downstream');
    SindhFlows.SukkurBarrage.WaterAccord = mapFlowData('SukkurBarrage_WaterAccord');
    SindhFlows.SukkurBarrage.Storage = mapFlowData('SukkurBarrage_Storage');
    SindhFlows.SukkurBarrage.Percent = mapFlowData('SukkurBarrage_Percent');
    SindhFlows.SukkurBarrage.PercentTotal = mapFlowData('SukkurBarrage_PercentTotal');
    SindhFlows.SukkurBarrage.AccordTotal = mapFlowData('SukkurBarrage_AccordTotal');
    SindhFlows.SukkurBarrage.ActualWD = mapFlowData('SukkurBarrage_ActualWD');
    SindhFlows.SukkurBarrage.ActualWDTotal = mapFlowData('SukkurBarrage_ActualWDTotal');
    SindhFlows.SukkurBarrage.RightBank_Level.US = mapFlowData('SukkurBarrage_Level_RightBank_Upstream');
    SindhFlows.SukkurBarrage.RightBank_Level.DS = mapFlowData('SukkurBarrage_Level_RightBank_Downstream');
    SindhFlows.SukkurBarrage.LeftBank_Level.US = mapFlowData('SukkurBarrage_Level_LeftBank_Upstream');
    SindhFlows.SukkurBarrage.LeftBank_Level.DS = mapFlowData('SukkurBarrage_Level_LeftBank_Downstream');

    mapCanals('SukkurBarrage', {
        NWCanal: 'NWCanal',
        RiceCanal: 'RiceCanal',
        DaduCanal: 'DaduCanal',
        NaraCanal: 'NaraCanal',
        RohriCanal: 'RohriCanal',
        KFEast: 'KFEast',
        KFWest: 'KFWest'
    });

    // Kotri Barrage
    SindhFlows.KotriBarrage.US = mapFlowData('KotriBarrage_upstream');
    SindhFlows.KotriBarrage.DS = mapFlowData('KotriBarrage_downstream');
    SindhFlows.KotriBarrage.WaterAccord = mapFlowData('KotriBarrage_WaterAccord');
    SindhFlows.KotriBarrage.Storage = mapFlowData('KotriBarrage_Storage');
    SindhFlows.KotriBarrage.Percent = mapFlowData('KotriBarrage_Percent');
    SindhFlows.KotriBarrage.ActualWD = mapFlowData('KotriBarrage_ActualWD');
    SindhFlows.KotriBarrage.RightBank_Level.US = mapFlowData('KotriBarrage_Level_RightBank_Upstream');
    SindhFlows.KotriBarrage.RightBank_Level.DS = mapFlowData('KotriBarrage_Level_RightBank_Downstream');
    SindhFlows.KotriBarrage.LeftBank_Level.US = mapFlowData('KotriBarrage_Level_LeftBank_Upstream');
    SindhFlows.KotriBarrage.LeftBank_Level.DS = mapFlowData('KotriBarrage_Level_LeftBank_Downstream');

    mapCanals('KotriBarrage', {
        KalriBegarFeeder: 'KalriBegarFeeder',
        AkramWah: 'AkramWah',
        Pinyari: 'Pinyari',
        Fuleli: 'Fuleli'
    });

    // Balochistan
    const balochistanMap = {
        BalochistanActual: 'BalochistanActual',
        GudduActualWD: 'GudduActualWD',
        GudduBarrage_Accord: 'GudduBarrage_Accord',
        KhirtharRD102: 'KhirtharRD102',
        Manhiti: 'Manhiti',
        PatRD109: 'PatRD109',
        UchDistry: 'UchDistry',
        Kachi: 'Kachi',
        Sindhwithdrawal: 'Sindhwithdrawal',
        SukkurActualWD: 'SukkurActualWD',
        SukkurBarrage_Accord: 'SukkurBarrage_Accord'
    };

    SindhFlows.Balochistan = {};
    Object.entries(balochistanMap).forEach(([jsonKey, targetKey]) => {
        SindhFlows.Balochistan[targetKey] = mapBalochFlowData(jsonKey);
    });
}
async function RenderLatestFlow() {
    const flowData = await loadFlow("https://api.hicsindh.pk/public/Flows/latestflow");

    if (!flowData || typeof flowData !== "object") {
        console.warn("Invalid flow data received.");
        return;
    }

    SindhFlows.LatestFlows.flowData = flowData;
    SindhFlows.LatestFlows.Date = flowData.sindh_dated?.split("T")[0] || "Unknown";
    SindhFlows.LatestFlows.DateJs = flowData.tarbela?.dateJs || "Unknown";

    const calcPercent = (actual, accord) => accord ? ((actual / accord) * 100).toFixed(2) : "0";

    // Barrage summaries
    SindhFlows.LatestFlows.GudduSummary = {
        US: flowData.gudduBarrage?.upstream,
        DS: flowData.gudduBarrage?.downstream,
        Accord: flowData.gudduBarrage?.accord,
        ActualWD: flowData.gudduBarrage?.withdrawal,
        Percent: calcPercent(flowData.gudduBarrage?.withdrawal, flowData.gudduBarrage?.accord),
        RightBank_Level: {
            US: flowData.gudduBarrage?.level_RightBank_Upstream,
            DS: flowData.gudduBarrage?.level_RightBank_Downstream
        },
        LeftBank_Level: {
            US: flowData.gudduBarrage?.level_LeftBank_Upstream,
            DS: flowData.gudduBarrage?.level_LeftBank_Downstream
        }
    };

    SindhFlows.LatestFlows.SukkurSummary = {
        US: flowData.sukkurBarrage?.upstream,
        DS: flowData.sukkurBarrage?.downstream,
        Accord: flowData.sukkurBarrage?.accord,
        ActualWD: flowData.sukkurBarrage?.withdrawal,
        Percent: calcPercent(flowData.sukkurBarrage?.withdrawal, flowData.sukkurBarrage?.accord),
        RightBank_Level: {
            US: flowData.sukkurBarrage?.level_RightBank_Upstream,
            DS: flowData.sukkurBarrage?.level_RightBank_Downstream
        },
        LeftBank_Level: {
            US: flowData.sukkurBarrage?.level_LeftBank_Upstream,
            DS: flowData.sukkurBarrage?.level_LeftBank_Downstream
        }
    };

    SindhFlows.LatestFlows.KotriSummary = {
        US: flowData.kotriBarrage?.upstream,
        DS: flowData.kotriBarrage?.downstream,
        Accord: flowData.kotriBarrage?.accord,
        ActualWD: flowData.kotriBarrage?.withdrawal,
        Percent: calcPercent(flowData.kotriBarrage?.withdrawal, flowData.kotriBarrage?.accord),
        RightBank_Level: {
            US: flowData.kotriBarrage?.level_RightBank_Upstream,
            DS: flowData.kotriBarrage?.level_RightBank_Downstream
        },
        LeftBank_Level: {
            US: flowData.kotriBarrage?.level_LeftBank_Upstream,
            DS: flowData.kotriBarrage?.level_LeftBank_Downstream
        }
    };

    // Canal summaries
    const canalGroups = {
        GudduCanals: {
            Rainee: flowData.rainee,
            BegarSindhFeeder: flowData.beghari,
            DesrtPatFeeder: flowData.desert,
            Ghotki: flowData.ghotki
        },
        SukkurCanals: {
            NWCanal: flowData.nw,
            RiceCanal: flowData.rice,
            DaduCanal: flowData.dadu,
            NaraCanal: flowData.nara,
            RohriCanal: flowData.rohri,
            KFEast: flowData.khpurE,
            KFWest: flowData.khpurW
        },
        KotriCanals: {
            KalriBegarFeeder: flowData.kb,
            AkramWah: flowData.akramWah,
            Pinyari: flowData.pinyari,
            Fuleli: flowData.fuleli
        }
    };

    for (const [groupKey, canals] of Object.entries(canalGroups)) {
        SindhFlows.LatestFlows[groupKey] = {};
        for (const [canalName, data] of Object.entries(canals)) {
            SindhFlows.LatestFlows[groupKey][canalName] = {
                Actual: data?.flows || 0,
                Accord: data?.accord || 0,
                Percent: calcPercent(data?.flows, data?.accord),
                Date: data?.dateJs || "Unknown"
            };
        }
    }

    // Reservoirs
    SindhFlows.LatestFlows.Reservoir = {
        Tarbela: {
            Level: flowData.tarbela?.level,
            Inflow: flowData.tarbela?.inflow,
            Outflow: flowData.tarbela?.outflow,
            Date: flowData.tarbela?.dateJs
        },
        Mangla: {
            Level: flowData.mangla?.level,
            Inflow: flowData.mangla?.inflow,
            Outflow: flowData.mangla?.outflow,
            Date: flowData.mangla?.dateJs
        },
        Kabul: {
            Discharge: flowData.kabul?.discharge,
            Level: flowData.kabul?.level,
            Date: flowData.kabul?.dateJs
        },
        Marala: {
            Inflow: flowData.marala?.inflow,
            Outflow: flowData.marala?.outflow,
            Date: flowData.marala?.dateJs
        },
        Kalabagh: {
            Level_US: flowData.kalabagh?.level_US,
            Level_DS: flowData.kalabagh?.level_DS,
            Withdrawals: flowData.kalabagh?.withdrawals,
            Inflow: flowData.kalabagh?.inflow,
            Outflow: flowData.kalabagh?.outflow,
            Date: flowData.kalabagh?.dateJs
        },
        Chashma: {
            Level_US: flowData.chashma?.level_US,
            Level_DS: flowData.chashma?.level_DS,
            Withdrawals: flowData.chashma?.withdrawals,
            Inflow: flowData.chashma?.inflow,
            Outflow: flowData.chashma?.outflow,
            Date: flowData.chashma?.dateJs
        },
        Taunsa: {
            Level_US: flowData.taunsa?.level_US,
            Level_DS: flowData.taunsa?.level_DS,
            Withdrawals: flowData.taunsa?.withdrawals,
            Inflow: flowData.taunsa?.inflow,
            Outflow: flowData.taunsa?.outflow,
            Date: flowData.taunsa?.dateJs
        }
    };

    // Link Canals
    SindhFlows.LatestFlows.LinkCanals = {
        Thal: {
            Flows: flowData.thal?.flows,
            Accord: flowData.thal?.accord,
            Date: flowData.thal?.dateJs
        },
        CJLink: {
            Flows: flowData.cjLink?.flows,
            Accord: flowData.cjLink?.accord,
            Date: flowData.cjLink?.dateJs
        },
        CRB: {
            Flows: flowData.crb?.flows,
            Accord: flowData.crb?.accord,
            Date: flowData.crb?.dateJs
        },
        DGKhan: {
            Flows: flowData.dgKhan?.flows,
            Accord: flowData.dgKhan?.accord,
            Date: flowData.dgKhan?.dateJs
        },
        MuzafarGarh: {
            Flows: flowData.muzafarGarh?.flows,
            Accord: flowData.muzafarGarh?.accord,
            Date: flowData.muzafarGarh?.dateJs
        },
        TPLink: {
            Flows: flowData.tpLink?.flows,
            Accord: flowData.tpLink?.accord,
            Date: flowData.tpLink?.dateJs
        }
    };

    // Tributaries
    SindhFlows.LatestFlows.Tributary = {
        Rasul: {
            Inflow: flowData.rasul?.inflow,
            Outflow: flowData.rasul?.outflow,
            Date: flowData.rasul?.dateJs
        },
        Qadirabad: {
            Inflow: flowData.qadirabad?.inflow,
            Outflow: flowData.qadirabad?.outflow,
            Date: flowData.qadirabad?.dateJs
        },
        Trimmu: {
            Inflow: flowData.trimmu?.inflow,
            Outflow: flowData.trimmu?.outflow,
            Date: flowData.trimmu?.dateJs
        },
        Balloki: {
            Inflow: flowData.balloki?.inflow,
            Outflow: flowData.balloki?.outflow,
            Date: flowData.balloki?.dateJs
        },

        Sidhnai: {
            Inflow: flowData.sidhnai?.inflow,
            Outflow: flowData.sidhnai?.outflow,
            Date: flowData.sidhnai?.dateJs
        },
        Sulemanki: {
            Inflow: flowData.sulemanki?.inflow,
            Outflow: flowData.sulemanki?.outflow,
            Date: flowData.sulemanki?.dateJs
        },
        Islam: {
            Inflow: flowData.islam?.inflow,
            Outflow: flowData.islam?.outflow,
            Date: flowData.islam?.dateJs
        }
    };

    console.log(`Latest flow data loaded into SindhFlows.LatestFlows for ${SindhFlows.LatestFlows.Date}`);
}
 



/**
  Reservoir
 */
// ---------------- Reservoir Charts ----------------
const ReservoirCharts = {
    Tarbela: function (title = "Tarbela at Indus", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tarbela.Inflow },
            { title: "Outflow", Values: PakFlow.Tarbela.Outflow },
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    },
    Kalabagh: function (title = "Kalabagh", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Kalabagh.Inflow },
            { title: "Outflow", Values: PakFlow.Kalabagh.Outflow },
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    },
    Chashma: function (title = "Chashma", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Chashma.Inflow },
            { title: "Outflow", Values: PakFlow.Chashma.Outflow },
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    },
    Taunsa: function (title = "Taunsa", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Taunsa.Inflow },
            { title: "Outflow", Values: PakFlow.Taunsa.Outflow },
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    },
    Panjnad: function (title = "Panjnad", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Panjnad.Inflow },
            { title: "Outflow", Values: PakFlow.Panjnad.Outflow },
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    },
    Kabul: function (title = "Kabul at Nowshera", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Kabul.Discharge },
            null,
            title,
            "chartTarbela",
            type,
            displayLabels,
            displayCount
        );
    }
  , Thal: function (title = "Thal", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.Thal.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    },
    CJLink: function (title = "CJLink", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.CJLink.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    },
    CRB: function (title = "CRB", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.CRB.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    },
    DGKhan: function (title = "DGKhan", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.DGKhan.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    },
    MuzafarGarh: function (title = "MuzafarGarh", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.MuzafarGarh.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    },
    TPLink: function (title = "TPLink", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Punjabwithdrawl.Dates_DD_MM_YY,
            { title: "Discharge", Values: PakFlow.Punjabwithdrawl.TPLink.flows },
            null,
            title,
            "chartThal",
            type,
            displayLabels,
            displayCount
        );
    }
  ,
    Mangla: function (title = "Mangla Dam", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.Mangla.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.Mangla.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Rasul: function (title = "Rasul", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.RASUL.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.RASUL.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Marala: function (title = "Marala", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.Marala.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.Marala.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Qadirabad: function (title = "Qadirabad", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.QADIRABAD.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.QADIRABAD.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Trimmu: function (title = "Trimmu", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.TRIMMU.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.TRIMMU.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Balloki: function (title = "Balloki", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.BALLOKI.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.BALLOKI.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Sidhnai: function (title = "Sidhnai", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.SIDHNAI.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.SIDHNAI.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Sulemanki: function (title = "Sulemanki", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.SULEMANKI.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.SULEMANKI.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    },
    Islam: function (title = "Islam", type = "line", displayLabels = false, displayCount = 60) {
        LoadCanalFlowChart(
            PakFlow.Tributry.Dates_DD_MM_YY,
            { title: "Inflow", Values: PakFlow.Tributry.ISLAM.Inflow },
            { title: "Outflow", Values: PakFlow.Tributry.ISLAM.Outflow },
            title,
            "chartRASUL",
            type,
            displayLabels,
            displayCount
        );
    }
};
 
async function LoadReservoirs() {
    let LatestFlowsLoaded = await RenderLatestFlow(); 
    let ReservoirsLoaded = await RenderReservoirs();
    let PunjabwithdrawlLoaded = await RenderPunjabwithdrawl();
    let TributryLoaded = await RenderTributry(); 
    LoadBackgroundCharts(6);  
    try {
        UpdateFlowStats(SindhFlows.LatestFlows);
    } catch (e) {
        console.log(e);
    }
    function LoadReservoirsFlow(PakFlow, tableID) {
        const fields = [
            "Tarbela_Level", "Tarbela_Inflow", "Tarbela_Outflow",
            "Kabul_Level", "Kabul_Discharge",
            "Kalabagh_Level_US", "Kalabagh_Level_DS", "Kalabagh_Inflow", "Kalabagh_Outflow",
            "Chashma_Level_US", "Chashma_Level_DS", "Chashma_Inflow", "Chashma_Outflow", "Chashma_Storage",
            "Taunsa_Level_US", "Taunsa_Level_DS", "Taunsa_Inflow", "Taunsa_Outflow",
            "Panjnad_Level_US", "Panjnad_Level_DS", "Panjnad_Inflow", "Panjnad_Outflow"
        ];

        const sourceMap = {
            Tarbela_Level: ["Tarbela", "Level"],
            Tarbela_Inflow: ["Tarbela", "Inflow"],
            Tarbela_Outflow: ["Tarbela", "Outflow"],
            Kabul_Level: ["Kabul", "Level"],
            Kabul_Discharge: ["Kabul", "Discharge"],
            Kalabagh_Level_US: ["Kalabagh", "Level_US"],
            Kalabagh_Level_DS: ["Kalabagh", "Level_DS"],
            Kalabagh_Inflow: ["Kalabagh", "Inflow"],
            Kalabagh_Outflow: ["Kalabagh", "Outflow"],
            Chashma_Level_US: ["Chashma", "Level_US"],
            Chashma_Level_DS: ["Chashma", "Level_DS"],
            Chashma_Inflow: ["Chashma", "Inflow"],
            Chashma_Outflow: ["Chashma", "Outflow"],
            Chashma_Storage: ["Chashma", "Storage"],
            Taunsa_Level_US: ["Taunsa", "Level_US"],
            Taunsa_Level_DS: ["Taunsa", "Level_DS"],
            Taunsa_Inflow: ["Taunsa", "Inflow"],
            Taunsa_Outflow: ["Taunsa", "Outflow"],
            Panjnad_Level_US: ["Panjnad", "Level_US"],
            Panjnad_Level_DS: ["Panjnad", "Level_DS"],
            Panjnad_Inflow: ["Panjnad", "Inflow"],
            Panjnad_Outflow: ["Panjnad", "Outflow"]
        };

        const getValue = (obj, path, index) => {
            const [section, key] = path;
            return obj?.[section]?.[key]?.[index] ?? "";
        };

        const totalDays = PakFlow.date.length;
        let html = "";

        for (let i = 0; i < totalDays; i++) {
            const datejs = PakFlow.Dates_DD_MM_YY[i] ?? "";
            const dt = new Date(PakFlow.date[i]);
            const monthjs = dt.toLocaleString("en-US", { month: "long" }) + "-" + dt.getFullYear();

            if (dt.getDate() === 1) {
                html += `<tr><th colspan="${fields.length + 2}" style="text-align:left">${monthjs}</th></tr>`;
            }

            let row = `<tr><th>${i + 1}</th><td class='text-nowrap'>${datejs}</td>`;
            fields.forEach(field => {
                row += `<td>${getValue(PakFlow, sourceMap[field], i)}</td>`;
            });
            row += `</tr>`;
            html += row;
        }

        $("#" + tableID).html(html);
        return true;
    }
    function LoadPunjabwithdrawl(PakPunjabwithdrawl, TableID) {
        const canalKeys = ["Thal", "CJLink", "CRB", "DGKhan", "MuzafarGarh", "TPLink"];
        const totalDays = PakPunjabwithdrawl.date.length;

        const tmpRow = `<tr><th>{sr}</th><td class='text-nowrap'>{datejs}</td>{canalCells}</tr>`;
        const tmpMonth = `<tr><th colspan="{span}" style="text-align:left">{month}</th></tr>`;
        let html = "";

        for (let i = 0; i < totalDays; i++) {
            const datejs = PakPunjabwithdrawl.Dates_DD_MM_YY[i] ?? "";
            const dt = new Date(PakPunjabwithdrawl.date[i]);
            const monthjs = dt.toLocaleString("en-US", { month: "long" }) + "-" + dt.getFullYear();

            if (dt.getDate() === 1) {
                html += tmpMonth.replace("{span}", canalKeys.length + 2).replace("{month}", monthjs);
            }

            const canalCells = canalKeys.map(key => {
                const flow = PakPunjabwithdrawl[key]?.flows?.[i] ?? "";
                return `<td>${flow}</td>`;
            }).join("");

            html += tmpRow
                .replace("{sr}", i + 1)
                .replace("{datejs}", datejs)
                .replace("{canalCells}", canalCells);

            try {
                Punjabwithdrawl_maincanals.date.push(dt.toLocaleDateString());
                canalKeys.forEach(key => {
                    const flow = PakPunjabwithdrawl[key]?.flows?.[i] ?? "";
                    Punjabwithdrawl_maincanals[key].Actual.push(flow);
                });
            } catch (ex) {
                // skip malformed entries
            }
        }

        $("#" + TableID).html(html);
        return true;
    }
    function LoadTributry(PakTributry, TableID) {
        const tributaryKeys = [
            { name: "Mangla", fields: ["Level", "Inflow", "Outflow"] },
            { name: "RASUL", fields: ["Inflow", "Outflow"] },
            { name: "Marala", fields: ["Inflow", "Outflow"] },
            { name: "QADIRABAD", fields: ["Inflow", "Outflow"] },
            { name: "TRIMMU", fields: ["Inflow", "Outflow"] },
            { name: "BALLOKI", fields: ["Inflow", "Outflow"] },
            { name: "SIDHNAI", fields: ["Inflow", "Outflow"] },
            { name: "SULEMANKI", fields: ["Inflow", "Outflow"] },
            { name: "ISLAM", fields: ["Inflow", "Outflow"] }
        ];

        const totalDays = PakTributry.date.length;
        const totalCols = 2 + tributaryKeys.reduce((sum, t) => sum + t.fields.length, 0);
        let html = "";

        for (let i = 0; i < totalDays; i++) {
            const dt = new Date(PakTributry.date[i]);
            const datejs = PakTributry.Dates_DD_MM_YY?.[i] ?? dt.toLocaleDateString("en-GB").replace(/\//g, "-");
            const monthjs = dt.toLocaleString("en-US", { month: "long" }) + "-" + dt.getFullYear();

            if (dt.getDate() === 1) {
                html += `<tr><th colspan="${totalCols}" style="text-align:left">${monthjs}</th></tr>`;
            }

            let row = `<tr><th>${i + 1}</th><td class='text-nowrap'>${datejs}</td>`;
            tributaryKeys.forEach(({ name, fields }) => {
                fields.forEach(field => {
                    const val = PakTributry[name]?.[field]?.[i] ?? "";
                    row += `<td>${val}</td>`;
                });
            });

            html += row + `</tr>`;
        }

        $("#" + TableID).html(html);
        return true;
    }
    function SetupPakTabs(strContainer) {
        var ContainerID = strContainer; //
        let Container = $('.' + ContainerID + '-container');
        if (Container) {
            let objFilter = $('#' + ContainerID + '-flters li');
            objFilter.click(function (e) {
                e.preventDefault();
                for (var a = 0; a < objFilter.length; a++) {
                    objFilter[a].classList.remove('filter-active');
                }
                this.classList.add('filter-active');
                if (this.getAttribute('data-filter') == ".filter-Tarbela") {  
                          ReservoirCharts.Tarbela(); 
                }

                else if (this.getAttribute('data-filter') == ".filter-Kalabagh") {
                  ReservoirCharts.Kalabagh(); 

      
                }
                else if (this.getAttribute('data-filter') == ".filter-Chashma") {
                   ReservoirCharts.Chashma(); 
                }
                else if (this.getAttribute('data-filter') == ".filter-Taunsa") { 
                  ReservoirCharts.Taunsa(); 
                }
                else if (this.getAttribute('data-filter') == ".filter-panjnad") {
                    ReservoirCharts.Panjnad(); 
                }
                else if (this.getAttribute('data-filter') == ".filter-Kabul") {
 
   ReservoirCharts.Kabul(); 
                    

                }
                else if (this.getAttribute('data-filter') == ".filter-thal") {
                  
                                           ReservoirCharts.Thal();

                }
                else if (this.getAttribute('data-filter') == ".filter-cj") {
                     ReservoirCharts.CJLink();
                }
                else if (this.getAttribute('data-filter') == ".filter-crb") {
                    ReservoirCharts.CRB();
                }
                else if (this.getAttribute('data-filter') == ".filter-dgkhan") {
                   ReservoirCharts.DGKhan();
              
                }
                else if (this.getAttribute('data-filter') == ".filter-mg") {
                    ReservoirCharts.MuzafarGarh();
                }
                else if (this.getAttribute('data-filter') == ".filter-tp") {
                    ReservoirCharts.TPLink();
                }
                else if (this.getAttribute('data-filter') == ".filter-Mangla") { 
                ReservoirCharts.Mangla();
                }

                else if (this.getAttribute('data-filter') == ".filter-Rasul") {
                      ReservoirCharts.Rasul();
                }
                else if (this.getAttribute('data-filter') == ".filter-Marala") {
                  ReservoirCharts.Marala();

                }
                else if (this.getAttribute('data-filter') == ".filter-Qadirabad") {
                     ReservoirCharts.Qadirabad();

                } else if (this.getAttribute('data-filter') == ".filter-Trimmu") {
                     ReservoirCharts.Trimmu();
                }

                else if (this.getAttribute('data-filter') == ".filter-Balloki") {
                     ReservoirCharts.Balloki();

                }
                else if (this.getAttribute('data-filter') == ".filter-Sidhnai") {
                  ReservoirCharts.Sidhnai();

                }
                else if (this.getAttribute('data-filter') == ".filter-Sulemanki") {
                    ReservoirCharts.Sulemanki();

                }
                else if (this.getAttribute('data-filter') == ".filter-Islam") {
                    ReservoirCharts.Islam();
                }

            })

        }
    }
    SetupPakTabs('ReservoirsPosition');
    SetupPakTabs('PunjabWithdrawls');
    SetupPakTabs('TributryRivers');
     
  
    let bReservoirsLoaded = LoadReservoirsFlow(PakFlow, "tblReservoirsPosition"); 
    let PunjabwithdrawlsLoaded = LoadPunjabwithdrawl(PakFlow.Punjabwithdrawl, "tblPunjabWithdrawls");
    let TributryLoaded1 = LoadTributry(PakFlow.Tributry, "tblTributryRivers");

    ReservoirCharts.Tarbela();
    ReservoirCharts.Thal();
    ReservoirCharts.Rasul(); 
    return true;
} 
/* Render Punjab Flows */
async function RenderReservoirs() {
    PakFlow.PakReservoirs = await loadFlow("https://api.hicsindh.pk/public/Flows/Reservoirs/Month/1")

    if (!Array.isArray(PakFlow.PakReservoirs) || PakFlow.PakReservoirs.length === 0) {
        console.warn("PakFlow.PakReservoirs is empty or invalid.");
        return;
    }

    const mapReservoirData = (resKey, propKey) =>
        PakFlow.PakReservoirs.map(item => item[resKey]?.[propKey] ?? null);

    PakFlow.Dates_DD_MM = PakFlow.PakReservoirs.map(item => moment(item.dated).format("DD-MMM"));
    PakFlow.Dates_DD_MM_YY = PakFlow.PakReservoirs.map(item => moment(item.dated).format("DD-MMM-YY"));
    PakFlow.date = PakFlow.PakReservoirs.map(item => new Date(item.dated));

    // Tarbela
    PakFlow.Tarbela.Inflow = mapReservoirData('tarbela', 'inflow');
    PakFlow.Tarbela.Outflow = mapReservoirData('tarbela', 'outflow');
    PakFlow.Tarbela.Level = mapReservoirData('tarbela', 'level');

    // Kabul
    PakFlow.Kabul.Discharge = mapReservoirData('kabul', 'discharge');
    PakFlow.Kabul.Level = mapReservoirData('kabul', 'level');

    // Kalabagh
    PakFlow.Kalabagh.Inflow = mapReservoirData('kalabagh', 'inflow');
    PakFlow.Kalabagh.Outflow = mapReservoirData('kalabagh', 'outflow');
    PakFlow.Kalabagh.Level_US = mapReservoirData('kalabagh', 'level_US');
    PakFlow.Kalabagh.Level_DS = mapReservoirData('kalabagh', 'level_DS');

    // Chashma
    PakFlow.Chashma.Inflow = mapReservoirData('chashma', 'inflow');
    PakFlow.Chashma.Outflow = mapReservoirData('chashma', 'outflow');
    PakFlow.Chashma.Level_US = mapReservoirData('chashma', 'level_US');
    PakFlow.Chashma.Level_DS = mapReservoirData('chashma', 'level_DS');
    PakFlow.Chashma.Storage = mapReservoirData('chashma', 'storage');
    PakFlow.Chashma.Withdrawals = mapReservoirData('chashma', 'withdrawals');

    // Taunsa
    PakFlow.Taunsa.Inflow = mapReservoirData('taunsa', 'inflow');
    PakFlow.Taunsa.Outflow = mapReservoirData('taunsa', 'outflow');
    PakFlow.Taunsa.Level_US = mapReservoirData('taunsa', 'level_US');
    PakFlow.Taunsa.Level_DS = mapReservoirData('taunsa', 'level_DS');

    // Panjnad
    PakFlow.Panjnad.Inflow = mapReservoirData('panjnad', 'inflow');
    PakFlow.Panjnad.Outflow = mapReservoirData('panjnad', 'outflow');
    PakFlow.Panjnad.Level_US = mapReservoirData('panjnad', 'level_US');
    PakFlow.Panjnad.Level_DS = mapReservoirData('panjnad', 'level_DS');
}

async function RenderPunjabwithdrawl() {
    PakFlow.PakPunjabwithdrawl = await loadFlow("https://api.hicsindh.pk/public/Flows/Punjabwithdrawls/Month/1")

    if (!Array.isArray(PakFlow.PakPunjabwithdrawl) || PakFlow.PakPunjabwithdrawl.length === 0) {
        console.warn("PakFlow.PakPunjabwithdrawl is empty or invalid.");
        return;
    }

    const mapWithdrawlData = (key, prop) =>
        PakFlow.PakPunjabwithdrawl.map(item => item[key]?.[prop] ?? null);

    PakFlow.Punjabwithdrawl.Dates_DD_MM = PakFlow.PakPunjabwithdrawl.map(item => moment(item.dated).format("DD-MMM"));
    PakFlow.Punjabwithdrawl.Dates_DD_MM_YY = PakFlow.PakPunjabwithdrawl.map(item => moment(item.dated).format("DD-MMM-YY"));
    PakFlow.Punjabwithdrawl.date = PakFlow.PakPunjabwithdrawl.map(item => new Date(item.dated));

    // CJLink
    PakFlow.Punjabwithdrawl.CJLink.flows = mapWithdrawlData('cjLink', 'flows');
    PakFlow.Punjabwithdrawl.CJLink.accord = mapWithdrawlData('cjLink', 'accord');

    // CRB
    PakFlow.Punjabwithdrawl.CRB.flows = mapWithdrawlData('crb', 'flows');
    PakFlow.Punjabwithdrawl.CRB.accord = mapWithdrawlData('crb', 'accord');

    // DGKhan
    PakFlow.Punjabwithdrawl.DGKhan.flows = mapWithdrawlData('dgKhan', 'flows');
    PakFlow.Punjabwithdrawl.DGKhan.accord = mapWithdrawlData('dgKhan', 'accord');

    // MuzafarGarh
    PakFlow.Punjabwithdrawl.MuzafarGarh.flows = mapWithdrawlData('muzafarGarh', 'flows');
    PakFlow.Punjabwithdrawl.MuzafarGarh.accord = mapWithdrawlData('muzafarGarh', 'accord');

    // TPLink
    PakFlow.Punjabwithdrawl.TPLink.flows = mapWithdrawlData('tpLink', 'flows');
    PakFlow.Punjabwithdrawl.TPLink.accord = mapWithdrawlData('tpLink', 'accord');

    // Thal
    PakFlow.Punjabwithdrawl.Thal.flows = mapWithdrawlData('thal', 'flows');
    PakFlow.Punjabwithdrawl.Thal.accord = mapWithdrawlData('thal', 'accord');
}

async function RenderTributry() {
    PakFlow.PakTributry = await loadFlow("https://api.hicsindh.pk/public/Flows/Tributry/Month/1")
    if (!Array.isArray(PakFlow.PakTributry) || PakFlow.PakTributry.length === 0) {
        console.warn("PakFlow.PakTributry is empty or invalid.");
        return false;
    }

    const mapTributryData = (key, prop) =>
        PakFlow.PakTributry.map(item => item[key]?.[prop] ?? null);

    PakFlow.Tributry.Dates_DD_MM = PakFlow.PakTributry.map(item => moment(item.dated).format("DD-MMM"));
    PakFlow.Tributry.Dates_DD_MM_YY = PakFlow.PakTributry.map(item => moment(item.dated).format("DD-MMM-YY"));
    PakFlow.Tributry.date = PakFlow.PakTributry.map(item => new Date(item.dated));

    // Mangla
    PakFlow.Tributry.Mangla.Inflow = mapTributryData('mangla', 'inflow');
    PakFlow.Tributry.Mangla.Outflow = mapTributryData('mangla', 'outflow');
    PakFlow.Tributry.Mangla.Level = mapTributryData('mangla', 'level');

    // Marala
    PakFlow.Tributry.Marala.Inflow = mapTributryData('marala', 'inflow');
    PakFlow.Tributry.Marala.Outflow = mapTributryData('marala', 'outflow');

    // QADIRABAD
    PakFlow.Tributry.QADIRABAD.Inflow = mapTributryData('qadirabad', 'inflow');
    PakFlow.Tributry.QADIRABAD.Outflow = mapTributryData('qadirabad', 'outflow');

    // RASUL
    PakFlow.Tributry.RASUL.Inflow = mapTributryData('rasul', 'inflow');
    PakFlow.Tributry.RASUL.Outflow = mapTributryData('rasul', 'outflow');

    // SIDHNAI
    PakFlow.Tributry.SIDHNAI.Inflow = mapTributryData('sidhnai', 'inflow');
    PakFlow.Tributry.SIDHNAI.Outflow = mapTributryData('sidhnai', 'outflow');

    // SULEMANKI
    PakFlow.Tributry.SULEMANKI.Inflow = mapTributryData('sulemanki', 'inflow');
    PakFlow.Tributry.SULEMANKI.Outflow = mapTributryData('sulemanki', 'outflow');

    // BALLOKI
    PakFlow.Tributry.BALLOKI.Inflow = mapTributryData('balloki', 'inflow');
    PakFlow.Tributry.BALLOKI.Outflow = mapTributryData('balloki', 'outflow');

    // ISLAM
    PakFlow.Tributry.ISLAM.Inflow = mapTributryData('islam', 'inflow');
    PakFlow.Tributry.ISLAM.Outflow = mapTributryData('islam', 'outflow');

    // TRIMMU
    PakFlow.Tributry.TRIMMU.Inflow = mapTributryData('trimmu', 'inflow');
    PakFlow.Tributry.TRIMMU.Outflow = mapTributryData('trimmu', 'outflow');
    return true;
}








/*  ****** Comparative ****** */  
const PakComparativeFlow = { 
    ReservoirsComparative: null,
    SindhBarragesComparative: null,
    ComparativeBarChartSearies: [],  
    Reservoirs: {
        ResDates: [],
        Tarbela: [],
        Chashma: [],
        Kalabagh: [],
        Panjnad: [],
        Taunsa: [],
        Kabul: []
    },
    SindhBarrages: {
        ResDates: [],
        Guddu: [],
        Sukkur: [],
        Kotri: []
    }
    
}; 
const PakComparativeCharts = {
    // ---------------- Reservoirs ----------------
    Tarbela: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Tarbela,
            "Tarbela Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Chashma: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Chashma,
            "Chashma Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Kalabagh: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Kalabagh,
            "Kalabagh Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Panjnad: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Panjnad,
            "Panjnad Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Taunsa: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Taunsa,
            "Taunsa Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Kabul: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.Reservoirs.ResDates,
            PakComparativeFlow.Reservoirs.Kabul,
            "Kabul Comparative Flow",
            "ChartReservoirComparative",
            "line",
            { mode: "flow", ShowDisplayType: true, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },

    // ---------------- Sindh Barrages ----------------
    Guddu: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.SindhBarrages.ResDates,
            PakComparativeFlow.SindhBarrages.Guddu,
            "Guddu Barrage Comparative Flow",
            "ChartSindhComparative",
            "line",
            { mode: "flow", ShowDisplayType: false, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Sukkur: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.SindhBarrages.ResDates,
            PakComparativeFlow.SindhBarrages.Sukkur,
            "Sukkur Barrage Comparative Flow",
            "ChartSindhComparative",
            "line",
            { mode: "flow", ShowDisplayType: false, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    },
    Kotri: function (options = {}) {
        LoadUnifiedFlowChart(
            PakComparativeFlow.SindhBarrages.ResDates,
            PakComparativeFlow.SindhBarrages.Kotri,
            "Kotri Barrage Comparative Flow",
            "ChartSindhComparative",
            "line",
            { mode: "flow", ShowDisplayType: false, DisplayLabels: false, DisplayValues: 30, ...options }
        );
    }
}; 
async function LoadComparativePage() { 
    function SetupCompareTabs(strContainer) {
        var ContainerID = strContainer; //
        let Container = $('.' + ContainerID + '-container');

        let objFilter = $('#' + ContainerID + '-flters li');
        objFilter.click(function (e) {
            e.preventDefault();
            for (var a = 0; a < objFilter.length; a++) {
                objFilter[a].classList.remove('filter-active');
            }
            this.classList.add('filter-active');

            if (this.getAttribute('data-filter') == ".filter-guddu") {
                PakComparativeCharts.Guddu();
            }
            else if (this.getAttribute('data-filter') == ".filter-Sukkur") {
                PakComparativeCharts.Sukkur();
            }
            else if (this.getAttribute('data-filter') == ".filter-Kotri") {
                PakComparativeCharts.Kotri();
            }
            else if (this.getAttribute('data-filter') == ".filter-Tarbela") {
                PakComparativeCharts.Tarbela({ DisplayValues: 30 });
            }

            else if (this.getAttribute('data-filter') == ".filter-Chasma") {
                PakComparativeCharts.Chashma({ DisplayValues: 30 });
            }
            else if (this.getAttribute('data-filter') == ".filter-Kalabagh") {
                PakComparativeCharts.Kalabagh({ DisplayValues: 30 });
            }
            else if (this.getAttribute('data-filter') == ".filter-Taunsa") {
                PakComparativeCharts.Taunsa({ DisplayValues: 30 });
            }

        })

    }

    function FillBanner(TableID) {
        function FillTable(_Tabel, _TableColIndex, DatasetR, DatasetS) {
            let obj_Cur_DS_RDate = moment(DatasetR.dated);
            let obj_Cur_DS_SDate = moment(DatasetS.dated);
            let formattedDate = obj_Cur_DS_RDate.format(DisplayFromate);
            let flows = new Array();
            _Tabel.tHead.rows[0].cells[_TableColIndex].innerHTML = formattedDate;

            _Tabel.tBodies[0].rows[1].cells[_TableColIndex].innerHTML = DatasetR.tarbela.level;
            _Tabel.tBodies[0].rows[2].cells[_TableColIndex].innerHTML = DatasetR.tarbela.inflow;
            _Tabel.tBodies[0].rows[3].cells[_TableColIndex].innerHTML = DatasetR.tarbela.outflow;

            flows.push(DatasetR.tarbela.inflow);
            flows.push(DatasetR.tarbela.outflow);


            _Tabel.tBodies[0].rows[5].cells[_TableColIndex].innerHTML = DatasetR.chashma.level_US;
            _Tabel.tBodies[0].rows[6].cells[_TableColIndex].innerHTML = DatasetR.chashma.level_DS;
            _Tabel.tBodies[0].rows[7].cells[_TableColIndex].innerHTML = DatasetR.chashma.inflow;
            _Tabel.tBodies[0].rows[8].cells[_TableColIndex].innerHTML = DatasetR.chashma.outflow;

            flows.push(DatasetR.chashma.inflow);
            flows.push(DatasetR.chashma.outflow);

            if (DatasetS != null &&
                obj_Cur_DS_RDate.isSame(obj_Cur_DS_SDate)) {
                _Tabel.tBodies[0].rows[10].cells[_TableColIndex].innerHTML = DatasetS.guddu.upstream;
                _Tabel.tBodies[0].rows[11].cells[_TableColIndex].innerHTML = DatasetS.guddu.downstream;

                flows.push(DatasetS.guddu.upstream);
                flows.push(DatasetS.guddu.downstream);

                _Tabel.tBodies[0].rows[13].cells[_TableColIndex].innerHTML = DatasetS.sukkur.upstream;
                _Tabel.tBodies[0].rows[14].cells[_TableColIndex].innerHTML = DatasetS.sukkur.downstream;

                flows.push(DatasetS.sukkur.upstream);
                flows.push(DatasetS.sukkur.downstream);

                _Tabel.tBodies[0].rows[16].cells[_TableColIndex].innerHTML = DatasetS.kotri.upstream;
                _Tabel.tBodies[0].rows[17].cells[_TableColIndex].innerHTML = DatasetS.kotri.downstream;

                flows.push(DatasetS.kotri.upstream);
                flows.push(DatasetS.kotri.downstream);
            }
            return { Date: formattedDate, flows: flows };
        }
        const _tblCompartive = document.getElementById(TableID);
        let arrYears = Object.keys(PakComparativeFlow.ReservoirsComparative).map(i => Number(i)).sort();
        let SYearKeys = Object.keys(PakComparativeFlow.SindhBarragesComparative).map(i => Number(i)).sort();
        if (!equals(arrYears, SYearKeys)) {
            console.log('unmatched values provided please check webapi');
            return;
        }
        try {
            let arrCurrentFlows = [];
            let arrPreviousFlows = [];
            const numofDisplayDate = 2;
            const CurrentYear = arrYears[arrYears.length - 1];
            const PreviousYear = arrYears[arrYears.length - 2];

            const Current_Reservoir_YearObj = PakComparativeFlow.ReservoirsComparative[CurrentYear];
            const ObjArray_SindhBarrage_CurItem = PakComparativeFlow.SindhBarragesComparative[CurrentYear];
            const obj_filtered_Reservoirs = Current_Reservoir_YearObj.slice(
                Math.max(Current_Reservoir_YearObj.length - (numofDisplayDate + 1), 0)
            );

            const ObjArray_Reservoir_PreviousItem = PakComparativeFlow.ReservoirsComparative[PreviousYear];
            const obj_filtered_Reservoirs_Previous = ObjArray_Reservoir_PreviousItem.slice(
                Math.max(ObjArray_Reservoir_PreviousItem.length - (numofDisplayDate + 1), 0)
            );

            const ObjArray_SindhBarrage_PreviousItem = PakComparativeFlow.SindhBarragesComparative[PreviousYear];
            const obj_filtered_SindhBarrage_Previous = ObjArray_SindhBarrage_PreviousItem.slice(
                Math.max(ObjArray_SindhBarrage_PreviousItem.length - (numofDisplayDate + 1), 0)
            );

            for (let i = 0; i < obj_filtered_Reservoirs.length; i++) {
                let colCurrentIndex = (i * numofDisplayDate) + numofDisplayDate;
                let obj_Cur_Reservoir = obj_filtered_Reservoirs[i];
                let obj_Cur_Barrage = ObjArray_SindhBarrage_CurItem.filter(el => el.dated == obj_Cur_Reservoir.dated);

                arrCurrentFlows.push(
                    FillTable(_tblCompartive, colCurrentIndex, obj_Cur_Reservoir, obj_Cur_Barrage[0])
                );

                let obj_Pre_Reservoir = obj_filtered_Reservoirs_Previous[i];
                let obj_Pre_Barrage = obj_filtered_SindhBarrage_Previous.filter(
                    el => moment(el.dated).isSame(moment(obj_Pre_Reservoir.dated))
                );

                arrPreviousFlows.push(
                    FillTable(_tblCompartive, colCurrentIndex - 1, obj_Pre_Reservoir, obj_Pre_Barrage[0])
                );
            }

            try {
                let SeariesList = [];
                for (let i = 0; i < arrCurrentFlows.length; i++) {
                    SeariesList.push(
                        { Year: CurrentYear, Date: arrCurrentFlows[i].Date, flows: arrCurrentFlows[i].flows },
                        { Year: PreviousYear, Date: arrPreviousFlows[i].Date, flows: arrPreviousFlows[i].flows }
                    );
                }
                PakComparativeFlow.ComparativeBarChartSearies = SeariesList;

            } catch (ex) {
                console.log("BarChartError", ex);
            }
        } catch (ex) {
            console.log("BarChartError", ex);
        }
    }
    function FillReservoirComparativeTable(TableID, comparativeData) {
        const years = Object.keys(comparativeData).map(y => parseInt(y)).sort((a, b) => b - a); // e.g. [2025, 2024, 2023]

        const reservoirs = [
            { name: "tarbela", fields: ["level", "inflow", "outflow"] },
            { name: "chashma", fields: ["level_US", "level_DS", "inflow", "outflow"] },
            { name: "kalabagh", fields: ["level_US", "level_DS", "inflow", "outflow"] },
            { name: "panjnad", fields: ["level_US", "level_DS", "inflow", "outflow"] },
            { name: "taunsa", fields: ["level_US", "level_DS", "inflow", "outflow"] },
            { name: "kabul", fields: ["discharge", "level"] }
        ];

        // Build thead
        let thead = `<thead class="table-light table-bordered border-dark border-1"><tr><th rowspan="3" class="align-middle">Date</th>`;
        reservoirs.forEach(res => {
            const colSpan = res.fields.length * years.length;
            thead += `<th colspan="${colSpan}" class="align-middle">${res.name.charAt(0).toUpperCase() + res.name.slice(1)}</th>`;
        });
        thead += `</tr><tr>`;
        reservoirs.forEach(res => {
            years.forEach(y => {
                thead += `<th colspan="${res.fields.length}">${y}</th>`;
            });
        });
        thead += `</tr><tr>`;
        reservoirs.forEach(res => {
            years.forEach(() => {
                res.fields.forEach(field => {
                    thead += `<th class="align-middle">${field.replace("_", " ")}</th>`;
                });
            });
        });
        thead += `</tr></thead>`;

        // Build tbody
        let tbody = "<tbody>";

        // Assume all year arrays are aligned by date index
        const rowCount = comparativeData[years[0]]?.length ?? 0;

        for (let i = 0; i < rowCount; i++) {
            const date = comparativeData[years[0]][i]?.dateJs ?? comparativeData[years[0]][i]?.dated?.split("T")[0] ?? `Row ${i + 1}`;
            let row = `<tr><td class="text-nowrap">${date}</td>`;

            reservoirs.forEach(res => {
                years.forEach(y => {
                    const entry = comparativeData[y]?.[i]?.[res.name] ?? {};
                    res.fields.forEach(field => {
                        row += `<td>${entry[field] ?? ""}</td>`;
                    });
                });
            });

            row += "</tr>";
            tbody += row;
        }

        tbody += "</tbody>";

        // Render table
        $("#" + TableID).html(`<table class="table table-sm table-bordered border-dark border-2">${thead}${tbody}</table>`);
    }
    function FillSindhBarragesComparativeTable(TableID, comparativeData) {
        const years = Object.keys(comparativeData)
            .map(y => parseInt(y))
            .sort((a, b) => b - a); // e.g. [2025, 2024, 2023]

        // Define Sindh barrages and the fields you want to display
        const sindhBarrages = [
            {
                name: "guddu", fields: ["upstream", "downstream"]
            },
            {
                name: "sukkur", fields: ["upstream", "downstream"]
            },
            {
                name: "kotri", fields: ["upstream", "downstream"]
            }
        ];

        // ---------------- Build thead ----------------
        let thead = `<thead class="table-light table-bordered border-dark border-1"><tr><th rowspan="3" class="align-middle">Date</th>`;
        sindhBarrages.forEach(barrage => {
            const colSpan = barrage.fields.length * years.length;
            thead += `<th colspan="${colSpan}" class="align-middle">${barrage.name.charAt(0).toUpperCase() + barrage.name.slice(1)}</th>`;
        });
        thead += `</tr><tr>`;
        sindhBarrages.forEach(barrage => {
            years.forEach(y => {
                thead += `<th colspan="${barrage.fields.length}">${y}</th>`;
            });
        });
        thead += `</tr><tr>`;
        sindhBarrages.forEach(barrage => {
            years.forEach(() => {
                barrage.fields.forEach(field => {
                    thead += `<th class="align-middle">${field.replace(/_/g, " ")}</th>`;
                });
            });
        });
        thead += `</tr></thead>`;

        // ---------------- Build tbody ----------------
        let tbody = "<tbody>";
        const rowCount = comparativeData[years[0]]?.length ?? 0;

        for (let i = 0; i < rowCount; i++) {
            const date = comparativeData[years[0]][i]?.dateJs
                ?? comparativeData[years[0]][i]?.dated?.split("T")[0]
                ?? `Row ${i + 1}`;
            let row = `<tr><td class="text-nowrap">${date}</td>`;

            sindhBarrages.forEach(barrage => {
                years.forEach(y => {
                    const entry = comparativeData[y]?.[i]?.[barrage.name] ?? {};
                    barrage.fields.forEach(field => {
                        row += `<td>${entry[field] ?? ""}</td>`;
                    });
                });
            });

            row += "</tr>";
            tbody += row;
        }
        tbody += "</tbody>";

        // ---------------- Render table ----------------
        $("#" + TableID).html(
            `<table class="table table-sm table-bordered border-dark border-2">${thead}${tbody}</table>`
        );
    }
     
    await RenderComparativeFlows();  
    if (document.getElementById("tblCompartive")) {
        FillBanner("tblCompartive");
    }
    if (document.getElementById("myChart")) {
        BarChart(PakComparativeFlow.ComparativeBarChartSearies, "myChart");
    }
    if (document.getElementById("tblReservoirComparative")) {
        FillReservoirComparativeTable("tblReservoirComparative", PakComparativeFlow.ReservoirsComparative);
    }
    if (document.getElementById("tblSindhComparative")) {
        FillSindhBarragesComparativeTable("tblSindhComparative", PakComparativeFlow.SindhBarragesComparative);
    }
    PakComparativeCharts.Tarbela({ DisplayValues: 30 });
    PakComparativeCharts.Guddu(); 
   
    try {

        SetupCompareTabs('SindhComparative');
        SetupCompareTabs('ReservoirComparative'); 
    }
    catch (ex) {
    } 
} 
async function RenderComparativeFlows() { 
    function BuildReservoirObjDB(comparativeData) {
        // 1. extract & sort years descending
        const years = Object.keys(comparativeData)
            .map(y => parseInt(y, 10))
            .sort((a, b) => b - a);

        // 2. sample the first year’s array and infer reservoir keys
        const firstYearArray = comparativeData[years[0]] || [];
        const reservoirKeys = firstYearArray.length
            ? Object.keys(firstYearArray[0]).filter(k =>
                !["id", "dated"].includes(k)
            )
            : [];

        // 3. seed objDB
        const objDB = { ResDates: [] };
        reservoirKeys.forEach(key => {
            const title = key.charAt(0).toUpperCase() + key.slice(1);
            objDB[title] = [];
        });

        // 4. build up ResDates and per-reservoir series
        years.forEach((yr, idx) => {
            const daily = comparativeData[yr] || [];

            // grab dates only once, using the first reservoir’s dateJs
            if (idx === 0 && reservoirKeys.length) {
                const firstKey = reservoirKeys[0];
                objDB.ResDates = daily.map(entry =>
                    entry[firstKey]?.dateJs
                    || entry.dated?.split("T")[0]   // fallback to ISO date if you like
                    || ""
                );
            }

            // now for each reservoir build inflow/downflow arrays
            reservoirKeys.forEach(key => {
                const title = key.charAt(0).toUpperCase() + key.slice(1);
                const up = [];
                const down = [];

                daily.forEach(entry => {
                    const d = entry[key] || {};
                    up.push(d.inflow ?? d.Inflow ?? 0);
                    down.push(d.outflow ?? d.Outflow ?? 0);
                });

                objDB[title].push({
                    Title: title,
                    Year: yr,
                    upstream: up,
                    downstream: down
                });
            });
        });

        return objDB;
    }
    function BuildSindhObjDB(sindhcomparativeData) {
        const objDB = { ResDates: [] };

        const years = Object.keys(sindhcomparativeData)
            .map(y => parseInt(y, 10))
            .sort((a, b) => b - a);

        const firstYearArray = sindhcomparativeData[years[0]] || [];
        const barrageKeys = firstYearArray.length
            ? Object.keys(firstYearArray[0]).filter(k => !["id", "dated", "dateJs", "monthJs"].includes(k))
            : [];

        barrageKeys.forEach(key => {
            const title = key.charAt(0).toUpperCase() + key.slice(1);
            objDB[title] = [];
        });

        years.forEach((yr, idx) => {
            const daily = sindhcomparativeData[yr] || [];

            if (idx === 0 && barrageKeys.length) {
                objDB.ResDates = daily.map(entry =>
                    entry.dateJs ||
                    entry.dated?.split("T")[0] ||
                    ""
                );
            }

            barrageKeys.forEach(key => {
                const title = key.charAt(0).toUpperCase() + key.slice(1);

                const up = [];
                const down = [];
                const withdrawal = [];
                const accord = [];
                const lvlLBUp = [];
                const lvlLBDown = [];
                const lvlRBUp = [];
                const lvlRBDown = [];

                daily.forEach(entry => {
                    const d = entry[key] || {};
                    up.push(d.upstream ?? 0);
                    down.push(d.downstream ?? 0);
                    withdrawal.push(d.withdrawal ?? 0);
                    accord.push(d.accord ?? 0);
                    lvlLBUp.push(d.level_LeftBank_Upstream ?? 0);
                    lvlLBDown.push(d.level_LeftBank_Downstream ?? 0);
                    lvlRBUp.push(d.level_RightBank_Upstream ?? 0);
                    lvlRBDown.push(d.level_RightBank_Downstream ?? 0);
                });

                objDB[title].push({
                    Title: title,
                    Year: yr,
                    upstream: up,
                    downstream: down,
                    withdrawal,
                    accord,
                    level_LeftBank_Upstream: lvlLBUp,
                    level_LeftBank_Downstream: lvlLBDown,
                    level_RightBank_Upstream: lvlRBUp,
                    level_RightBank_Downstream: lvlRBDown
                });
            });
        });

        return objDB;
    } 
    PakComparativeFlow.ReservoirsComparative = await loadFlow("https://api.hicsindh.pk/public/Flows/Comparative/Reservoirs");
    PakComparativeFlow.SindhBarragesComparative = await loadFlow("https://api.hicsindh.pk/public/Flows/Comparative/SindhBarrages");
     
    PakComparativeFlow.Reservoirs = BuildReservoirObjDB(PakComparativeFlow.ReservoirsComparative);
    PakComparativeFlow.SindhBarrages = BuildSindhObjDB(PakComparativeFlow.SindhBarragesComparative);
   
} 
  




/*

**** Lakes ****


*/

/* Lakes */
const Lakes = {
    Lakesobj: [],
    Chotiariobj: null,
    Lake_Cur_Dates: [],
    MancharLake: [],
    Kinjharlake: [],
    NaiGaj: [],
    DaduMoro: [], 
    Chotiari_Cur_Dates: [],
    Chotiari_Reservoir: [],
    Chotiari_Gauge: [],
    Chotiari_Ranto: []
}; 
const ChotiariCharts = {
    Reservoir: function ({ chartId, chartType = "line", DisplayLabels = false, DisplayValues = 20 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Dates_DD_MM_YY,
            Lakes.Chotiari_Reservoir,
            "Chotiari Reservoir Level",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels  : false, DisplayValues: 0 }
        );
    },
    Gauge: function ({ chartId, chartType = "line", DisplayLabels = false, DisplayValues = 0 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Dates_DD_MM_YY,
            Lakes.Chotiari_Gauge,
            "Chotiari Reservoir Gauge",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    },
    Ranto: function ({ chartId, chartType = "bar", DisplayLabels = false, DisplayValues = 0 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Dates_DD_MM_YY,
            Lakes.Chotiari_Ranto,
            "Chotiari Ranto Canal",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    }
};
async function LoadChotiari(chartId, btnReservoirLevelID, btnReservoirGaugeID, btnRantoID) {
    await RenderChotiari();

    const chartConfigs = {
        [btnReservoirLevelID]: {
            data: Lakes.Chotiari_Reservoir,
            title: "Reservoir Level",
            type: "line",
            options: { mode: "historical", DisplayLabels: false, DisplayValues: 0 }
        },
        [btnReservoirGaugeID]: {
            data: Lakes.Chotiari_Gauge,
            title: "Reservoir Gauge",
            type: "line",
            options: { mode: "historical", DisplayLabels: false, DisplayValues: 0 }
        },
        [btnRantoID]: {
            data: Lakes.Chotiari_Ranto,
            title: "Ranto Canal",
            type: "bar",
            options: { mode: "historical", DisplayLabels: false, DisplayValues: 0 }
        }
    };

    Object.entries(chartConfigs).forEach(([btnId, config]) => {
        $("#" + btnId).off("click").on("click", () => {
            LoadUnifiedFlowChart(
                Lakes.Chotiari_Cur_Dates,
                config.data,
                config.title,
                chartId,
                config.type,
                config.options
            );
        });
    });

    $("#" + btnReservoirLevelID).click();  
}
async function RenderChotiari() {
    let currentYear = new Date().getFullYear();
    if (isNaN(currentYear) || currentYear < 2020 || currentYear > 2100) {
        currentYear = 2025; // fallback if system date is invalid
    }

    const startYear = 2020;
    const yearList = Array.from({ length: currentYear - startYear + 1 }, (_, i) => startYear + i);
    const yearParam = yearList.join(",");

    const response = await loadFlow(`https://api.hicsindh.pk/public/reservoir/years/${yearParam}`);
 

   // const response = await loadFlow("/api/gauge/chotiari/years/2020,2021,2022,2023,2024,2025");
    Lakes.Chotiariobj = response;

    const sortedYears = Object.keys(response).map(Number).sort();
    const latestYear = sortedYears[sortedYears.length - 2];
    const latestData = response[latestYear];

    Lakes.Chotiari_Cur_Dates = latestData.map(item => moment(item.dated).format("DD-MMM"));

    Lakes.Chotiari_Reservoir = [];
    Lakes.Chotiari_Gauge = [];
    Lakes.Chotiari_Ranto = [];

    for (const [year, data] of Object.entries(response)) {
        const yearNum = Number(year);
        Lakes.Chotiari_Reservoir.push({ year: yearNum, data: data.map(item => item.reservoirLevel) });
        Lakes.Chotiari_Gauge.push({ year: yearNum, data: data.map(item => item.gauge) });
        Lakes.Chotiari_Ranto.push({ year: yearNum, data: data.map(item => item.ranto) });
        //Remarks
    }
    return true;
}
 
const LakesCharts = {
    Manchar: function ({ chartId, chartType = "line", DisplayLabels = false, DisplayValues = 20 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Cur_Dates,
            Lakes.MancharLake,
            "Manchar Lake",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    },
    DaduMoro: function ({ chartId, chartType = "bar", DisplayLabels = false, DisplayValues = 20 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Cur_Dates,
            Lakes.DaduMoro,
            "Dadu Moro Bridge Gauge",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    },
    Kinjhar: function ({ chartId, chartType = "line", DisplayLabels = false, DisplayValues = 20 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Cur_Dates,
            Lakes.Kinjharlake,
            "Kinjhar Lake",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    },
    NaiGaj: function ({ chartId, chartType = "bar", DisplayLabels = false, DisplayValues = 20 } = {}) {
        LoadUnifiedFlowChart(
            Lakes.Lake_Cur_Dates,
            Lakes.NaiGaj,
            "Nai Gaj Gauge",
            chartId,
            chartType,
            { mode: "historical", DisplayLabels, DisplayValues }
        );
    }
}; 
async function LoadLakePage() {
    await RenderLakeData()
    $("#btnMancharLevel").click(function () {
        LakesCharts.Manchar({ chartId: "ChartMancharLake", chartType: 'line', DisplayLabels: false, DisplayValues: 0 });
 
    });
    $("#btnDaduGauge").click(function () {
        LakesCharts.DaduMoro({ chartId: "ChartMancharLake", chartType: 'bar', DisplayLabels: false, DisplayValues: 0 });
         
    });
    $("#btnMancharLevel").click();
    window.setTimeout(
        function () {
            LakesCharts.Kinjhar({ chartId: "ChartKinjharlake", chartType: 'line', DisplayLabels: false, DisplayValues: 0 });
             
        }, 1000);;
    window.setTimeout(
        function () {
            LakesCharts.NaiGaj({ chartId: "ChartNaiGaj", chartType: 'bar', DisplayLabels: false, DisplayValues: 0 });
 
        }, 1500);



   
}
async function RenderLakeData() {
    let currentYear = new Date().getFullYear();
    if (isNaN(currentYear) || currentYear < 2025 || currentYear > 2030) {
        currentYear = 2025; // fallback if system date is invalid
    }

    const startYear = 2024;
    const yearList = Array.from({ length: currentYear - startYear + 1 }, (_, i) => startYear + i);
    const yearParam = yearList.join(",");

    Lakes.Lakesobj = await loadFlow(`https://api.hicsindh.pk/public/lakes/years/2018,2019,2023,` + yearParam);
     
    /** Lakes **/
    const arrYears = Object.keys(Lakes.Lakesobj).map(Number).sort();
    const latestYearData = Lakes.Lakesobj[arrYears[arrYears.length - 1]];
    Lakes.Lake_Cur_Dates = latestYearData.map(item => moment(item.dated).format("DD-MMM"));
    Lakes.Lake_Dates_DD_MM_YY = latestYearData.map(item => moment(item.dated).format("DD-MMM-YY"));

    for (const [year, data] of Object.entries(Lakes.Lakesobj)) {
        const yearNum = Number(year);
        Lakes.MancharLake.push({ year: yearNum, data: data.map(item => item.mancharLake) });
        Lakes.Kinjharlake.push({ year: yearNum, data: data.map(item => item.kinjharlake) });
        Lakes.NaiGaj.push({ year: yearNum, data: data.map(item => item.naiGaj) });
        Lakes.DaduMoro.push({ year: yearNum, data: data.map(item => item.daduMoro) });
    }
}



async function loadFlow(url, maxRetries = 5, delayMs = 500) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`Attempt ${attempt} to fetch: ${url}`);

            const response = await fetch(url, {
                method: "GET",
                mode: "cors",
                cache: "no-cache",
                headers: {
                    "Accept": "application/json"
                    // Removed Content-Type for GET to avoid unnecessary preflight
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            console.log("✅ Data loaded successfully");
            return data;

        } catch (error) {
            console.error(`❌ Attempt ${attempt} failed:`, error);

            if (attempt < maxRetries) {
                console.log(`⏳ Retrying in ${delayMs}ms...`);
                await new Promise(res => setTimeout(res, delayMs));
            } else {
                console.error("🚫 All attempts failed.");
                return null;
            }
        }
    }
}

const objCharts = [];
function CreateChart(x, Series, Title, desc, chartid, ChartType, horizontal = false) {
    const chartElement = document.getElementById(chartid);

    if (!chartElement) { 
        console.log("No chart element found with ID:", chartid);
        return;
    }  


    const labels = x;
    const data = {
        labels: labels,
        datasets: Series
    };

    const ctx = document.getElementById(chartid).getContext('2d');
    const totalPoints = Series.reduce((sum, s) => sum + s.data.length, 0);
    const baseDelay = totalPoints > 50 ? 10 : 400;
    let animation;
    if (ChartType === "bar") {
        let delayed = false;
        animation = {
            onComplete: () => { delayed = true; },
            delay: (context) => {
                let delay = 0;
                

                if (context.type === 'data' && context.mode === 'default' && !delayed) {
                    delay = context.dataIndex * baseDelay + context.datasetIndex * 100;
                }
                return delay;
            }
        };
    } else if (ChartType === "line") {
        const totalDuration = 1000;
        const delayBetweenPoints = totalDuration / Series[0].data.length;
        const previousY = (ctx) =>
            ctx.index === 0
                ? ctx.chart.scales.y.getPixelForValue(Series[0].data[0])
                : ctx.chart.getDatasetMeta(ctx.datasetIndex).data[ctx.index - 1].getProps(['y'], true).y;

        animation = {
            x: {
                type: 'number',
                easing: 'linear',
                duration: delayBetweenPoints,
                from: NaN,
                delay(ctx) {
                    if (ctx.type !== 'data' || ctx.xStarted) return 0;
                    ctx.xStarted = true;
                    return ctx.index * delayBetweenPoints;
                }
            },
            y: {
                type: 'number',
                easing: 'linear',
                duration: delayBetweenPoints,
                from: previousY,
                delay(ctx) {
                    if (ctx.type !== 'data' || ctx.yStarted) return 0;
                    ctx.yStarted = true;
                    return ctx.index * delayBetweenPoints;
                }
            }
        };
    } else {
        animation = { duration: 1000, easing: 'easeOutQuart' };
    }

    const chartOptions = {
        indexAxis: horizontal ? 'y' : 'x',
        animation,
        responsive: true,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        stacked: false,
        plugins: {
            title: {
                display: false,
                text: Title
            },
            legend: { position: 'top' }
        },
        scales: {
            x: { beginAtZero: true },
            y: { type: horizontal ? 'category' : 'linear', display: true }
        }
    };

    if (!objCharts[chartid]) {
        objCharts[chartid] = new Chart(ctx, {
            type: ChartType,
            data: data,
            options: chartOptions
        });
    } else {
        const chart = objCharts[chartid];
        chart.options.plugins.title.text = Title;
        chart.config.type = ChartType;
        chart.options.indexAxis = horizontal ? 'y' : 'x';
        chart.options.animation = animation;
        chart.data = data;
        chart.update();
    }
}

 
function BarChart(SeariesList, chartid) {
    const ChartColors = [
        { backgroundColor: 'rgba(54, 162, 235, 0.2)', borderColor: 'rgba(54, 162, 235, 1)' },
        { backgroundColor: 'rgba(255, 99, 132, 0.2)', borderColor: 'rgba(255, 99, 132, 1)' },
        { backgroundColor: 'rgba(196, 231, 55, 0.2)', borderColor: 'rgba(196, 231, 55, 1)' },
        { backgroundColor: 'rgba(68, 231, 55, 0.2)', borderColor: 'rgba(68, 231, 55, 1)' },
        { backgroundColor: 'rgba(55, 231, 229, 0.2)', borderColor: 'rgba(55, 231, 229, 1)' },
        { backgroundColor: 'rgba(42, 87, 139, 0.2)', borderColor: 'rgba(42, 87, 139, 1)' },
        { backgroundColor: 'rgba(117, 134, 42, 0.2)', borderColor: 'rgba(117, 134, 42, 1)' },
        { backgroundColor: 'rgba(38, 116, 78, 0.2)', borderColor: 'rgba(38, 116, 78, 1)' }
    ];
    const labels = [
        'Tarbela Inflow', 'Tarbela Outflow', 'Chasma Inflow', 'Chasma Outflow',
        'Guddu Barrage US', 'Guddu Barrage DS', 'Sukkur Barrage US', 'Sukkur Barrage DS',
        'Kotri Barrage US', 'Kotri Barrage DS'
    ];

    const DataSets = SeariesList.map((item, index) => {
        const color = ChartColors[(SeariesList.length - 1 - index) % ChartColors.length];
        return {
            label: item.Date,
            data: item.flows,
            backgroundColor: color.backgroundColor,
            borderColor: color.borderColor,
            borderWidth: 1,
            hidden: index <= (SeariesList.length - 3)
        };
    });

    CreateChart(labels, DataSets, "Water Flows Comparative Chart", "Source : Director Regulation", chartid, "bar", true);
}
/* Chart  */

function LoadCanalFlowChart(x, Series1, Series2, title, chartid, ChartType, DisplayLabels, DisplayValues) {
    const X_Chart = DisplayValues > 0 ? x.slice(-DisplayValues) : x;
    const y1 = DisplayValues > 0 ? Series1.Values.slice(-DisplayValues) : Series1.Values;
    const Series = [];
    const rotation = ChartType === "bar" ? 90 : 0;
    const _DisplayLabels = DisplayLabels === true;
    const createSeries = (series, color) => ({
        label: series.title,
        data: series.Values.slice(-DisplayValues),
        borderColor: color,
        backgroundColor: color,
        datalabels: {
            display: _DisplayLabels,
            align: ChartType === "bar" ? 'center' : 'end',
            anchor: ChartType === "bar" ? 'center' : 'end',
            rotation: rotation,
            clamp: true,
            color: ChartType === "bar" ? 'white' : 'black'
        }
    });

    Series.push(createSeries(Series1, 'rgba(255, 99, 132, 1)'));

    if (Series2) {
        Series.push(createSeries(Series2, 'rgba(75, 192, 192, 1)'));
    }

    CreateChart(X_Chart, Series, title, "Source : Director Regulation", chartid, ChartType);
}
 
function LoadUnifiedFlowChart(dates, dataInput, title, chartid, chartType = "line", options = {}) {
    const {
        DisplayLabels = false,
        DisplayValues = 0,
        ShowDisplayType = false,
        mode = "historical" // "flow" or "historical"
    } = options;

    const X_Chart = DisplayValues > 0 ? dates.slice(-DisplayValues) : dates;
    const rotation = chartType === "bar" ? 90 : 0;

    const colors = [
        { backgroundColor: "rgba(38,116,78,0.2)", borderColor: "rgba(38,116,78,1)" },
        { backgroundColor: "rgba(54,162,235,0.2)", borderColor: "rgba(54,162,235,1)" },
        { backgroundColor: "rgba(255,99,132,0.2)", borderColor: "rgba(255,99,132,1)" },
        { backgroundColor: "rgba(255,206,86,0.2)", borderColor: "rgba(255,206,86,1)" },
        { backgroundColor: "rgba(68,231,55,0.2)", borderColor: "rgba(68,231,55,1)" },
        { backgroundColor: "rgba(196,231,55,0.2)", borderColor: "rgba(196,231,55,1)" },
        { backgroundColor: "rgba(55,231,229,0.2)", borderColor: "rgba(55,231,229,1)" },
        { backgroundColor: "rgba(42,87,139,0.2)", borderColor: "rgba(42,87,139,1)" }
    ];

    const LabelUS = ShowDisplayType ? " Inflow " : " US ";
    const LabelDS = ShowDisplayType ? " Outflow " : " DS ";

    const makeDatalabels = () => ({
        display: DisplayLabels,
        align: chartType === "bar" ? "center" : "end",
        anchor: chartType === "bar" ? "center" : "end",
        rotation,
        clamp: true,
        color: chartType === "bar" ? "white" : "black"
    });

    const Series = [];

    if (mode === "historical") {
        dataInput.forEach((item, index) => {
            const color = colors[(dataInput.length - 1 - index) % colors.length];
            Series.push({
                label: item.year,
                data: DisplayValues > 0 ? item.data.slice(-DisplayValues) : item.data,
                ...color,
                borderWidth: 1,
                datalabels: makeDatalabels(),
                hidden: item.year <= 2021 && chartType !== "line"
            });
        });
    }

    if (mode === "flow") {
        dataInput.forEach((item, index) => {
            const color = colors[(dataInput.length - 1 - index) % colors.length];

            Series.push({
                label: `${item.Title}${LabelUS}${item.Year}`,
                data: DisplayValues > 0 ? item.upstream.slice(-DisplayValues) : item.upstream,
                ...color,
                borderWidth: 1,
                datalabels: makeDatalabels()
            });

            Series.push({
                label: `${item.Title}${LabelDS}${item.Year}`,
                data: DisplayValues > 0 ? item.downstream.slice(-DisplayValues) : item.downstream,
                ...color,
                borderWidth: 1,
                datalabels: makeDatalabels()
            });
        });
    }

    CreateChart(X_Chart, Series, title.toUpperCase(), "Source : Director Regulation", chartid, chartType);
}

function LoadBackgroundCharts(NoofCharts = 4, customData = null, customLabels = null) {
    const randomData = () => Array.from({ length: 7 }, () => Math.floor(Math.random() * 10));

    const boSmallStatsDatasets = [
        { backgroundColor: 'rgba(0, 184, 216, 0.1)', borderColor: 'rgb(0, 184, 216)', data: randomData() },
        { backgroundColor: 'rgba(23,198,113,0.1)', borderColor: 'rgb(23,198,113)', data: randomData() },
        { backgroundColor: 'rgba(255,180,0,0.1)', borderColor: 'rgb(255,180,0)', data: randomData() },
        { backgroundColor: 'rgba(255,65,105,0.1)', borderColor: 'rgb(255,65,105)', data: randomData() },
        { backgroundColor: 'rgba(0,123,255,0.1)', borderColor: 'rgb(0,123,255)', data: randomData() },
        { backgroundColor: 'rgba(255,65,105,0.1)', borderColor: 'rgb(255,65,105)', data: randomData() },
        { backgroundColor: 'rgba(255,180,0,0.1)', borderColor: 'rgb(255,180,0)', data: randomData() },
        { backgroundColor: 'rgba(0, 184, 216, 0.1)', borderColor: 'rgb(0, 184, 216)', data: randomData() },
        { backgroundColor: 'rgba(255,180,0,0.1)', borderColor: 'rgb(255,180,0)', data: randomData() }
    ].slice(0, NoofCharts);

    const datasetsToUse = customData || boSmallStatsDatasets;
    const labelsToUse = customLabels || Array(7).fill(""); // empty labels

    try {
        datasetsToUse.forEach((el, index) => {
            const canvas = document.querySelector('canvas.blog-overview-stats-small-' + (index + 1));
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labelsToUse,
                    datasets: [{
                        label: '', // no dataset label
                        fill: 'start',
                        data: el.data || randomData(),
                        backgroundColor: el.backgroundColor,
                        borderColor: el.borderColor,
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.4
                    }]
                },
                options: {
                    maintainAspectRatio: true,
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false },
                        datalabels: { display: false }
                    },
                    elements: {
                        point: { radius: 0 }
                    },
                    scales: {
                        x: {
                            display: false,
                            ticks: { display: false },
                            grid: { display: false }
                        },
                        y: {
                            display: false,
                            ticks: { display: false },
                            grid: { display: false }
                        }
                    }
                }
            });
        });
    } catch (e) {
        console.error("Chart error:", e);
    }
}

function LoadHistroicalFlowChart(x, SeriesDataSet, title, chartid, ChartType, DisplayLabels, DisplayValues) {
    const X_Chart = DisplayValues > 0 ? x.slice(-DisplayValues) : x;
    const Series = [];
    const rotation = ChartType === "bar" ? 90 : 0;
    const _DisplayLabels = DisplayLabels === true;
    const createSeries = (series, color) => ({
        label: series.title,
        data: series.Values.slice(-DisplayValues),
        borderColor: color.borderColor,
        backgroundColor: color.backgroundColor,
        datalabels: {
            display: _DisplayLabels,
            align: ChartType === "bar" ? 'center' : 'end',
            anchor: ChartType === "bar" ? 'center' : 'end',
            rotation: rotation,
            clamp: true,
            color: ChartType === "bar" ? 'white' : 'black'
        }
    });
    const Colors = new Array();

    Colors.push({

        backgroundColor: 'rgba(38, 116, 78, 1)',
        borderColor: 'rgba(38, 116, 78, 1)'
    });
    Colors.push({
        backgroundColor: 'rgba(54, 162, 235,1)',
        borderColor: 'rgba(54, 162, 235, 1)'
    });
    Colors.push({
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 1)'
    });
    let Count = 0;
    for (const [Index, data] of Object.entries(SeriesDataSet)) {
        Series.push(createSeries({ title: data.year, Values: data.data }, Colors[Index]));
        Count++;
    }

    CreateChart(X_Chart, Series, title, "Source : Director Regulation", chartid, ChartType);
}



/* Lagacey Code */


//function ScreenGuddu() {
//    stopCallingFunctions();
//    startCallingGuddu(true);
//    $('#option_b1').prop('checked', true);
//    $('.btn').removeClass('active');
//    $('#option_b1').closest('.btn').addClass('active');

//    /* Loading Static Data */
//    $("#ChartLeftTitle").fadeOut(function () { $(this).text("Guddu Barrage").fadeIn(); });

//    $("#Box1Left .stats-small__label").html("Discharge");
//    $("#Box1Left .sub_label").html("Actual : " + SindhFlows.GudduBarrage.ActualWDTotal.at(-1) +
//        " / Accord : " + SindhFlows.GudduBarrage.WaterAccord.at(-1));

//    $("#Box1Left .stats-small__value").html(
//        SindhFlows.GudduBarrage.US.at(-1) + "/" +
//        SindhFlows.GudduBarrage.DS.at(-1)
//    );
//    const TotalPercent = SindhFlows.GudduBarrage.TotalPercent.at(-1);
//    $("#Box1Left .stats-small__percentage").html(TotalPercent + "%");
//    $("#Box1Left .stats-small__percentage").removeClass()
//        .addClass("stats-small__percentage");
//    if (TotalPercent > 0) {
//        $("#Box1Left .stats-small__percentage").addClass("stats-small__percentage--increase");
//    } else if (TotalPercent < 0) {
//        $("#Box1Left .stats-small__percentage").addClass("stats-small__percentage--decrease");
//    }
//    else {
//        $("#Box1Left .stats-small__percentage").addClass("stats-small__percentage--still");
//    }

//    $("#Box2Left .stats-small__label").html("Right Bank Level");

//    $("#Box2Left .stats-small__value").html(
//        SindhFlows.GudduBarrage.RightBank_Level.US.at(-1) + "/" +
//        SindhFlows.GudduBarrage.RightBank_Level.DS.at(-1)
//    );

//    $("#Box2Left .stats-small__percentage").html("");
//    $("#Box2Left .stats-small__percentage").removeClass()
//        .addClass("stats-small__percentage");


//    $("#Box3Left .stats-small__label").html("Left Bank Level");

//    $("#Box3Left .stats-small__value").html(
//        SindhFlows.GudduBarrage.LeftBank_Level.US.at(-1) + "/" +
//        SindhFlows.GudduBarrage.LeftBank_Level.DS.at(-1)
//    );

//    $("#Box3Left .stats-small__percentage").html("");
//    $("#Box3Left .stats-small__percentage").removeClass()
//        .addClass("stats-small__percentage");

//    swiper.removeAllSlides();
//    try {
//        swiper.appendSlide(getSlide("Desert Pat Feeder",
//            SindhFlows.GudduBarrage.DesrtPatFeeder.Actual.at(-1),
//            SindhFlows.GudduBarrage.DesrtPatFeeder.WaterAccord.at(-1),
//            SindhFlows.GudduBarrage.DesrtPatFeeder.Percent.at(-1),
//            SindhFlows.GudduBarrage.DesrtPatFeeder.Remarks.at(-1)
//        ));
//        console.log(SindhFlows.GudduBarrage.BegarSindhFeeder.Percent.at(-1));
//        console.log(SindhFlows.GudduBarrage.BegarSindhFeeder.Remarks.at(-1));
//        swiper.appendSlide(getSlide("Begar Sindh Feeder",
//            SindhFlows.GudduBarrage.BegarSindhFeeder.Actual.at(-1),
//            SindhFlows.GudduBarrage.BegarSindhFeeder.WaterAccord.at(-1),
//            SindhFlows.GudduBarrage.BegarSindhFeeder.Percent.at(-1),
//            SindhFlows.GudduBarrage.BegarSindhFeeder.Remarks.at(-1)
//        ));
//        swiper.appendSlide(getSlide("Ghotki Feeder",
//            SindhFlows.GudduBarrage.Ghotki.Actual.at(-1),
//            SindhFlows.GudduBarrage.Ghotki.WaterAccord.at(-1),
//            SindhFlows.GudduBarrage.Ghotki.Percent.at(-1),
//            SindhFlows.GudduBarrage.Ghotki.Remarks.at(-1)
//        ));
//        swiper.appendSlide(getSlide("Ranee Canal",
//            SindhFlows.GudduBarrage.Rainee.Actual.at(-1),
//            SindhFlows.GudduBarrage.Rainee.WaterAccord.at(-1),
//            0,
//            ""
//        ));
//    }
//    catch (ex) {
//        console.log(ex);
//    }
//    //console.log("Percent", SindhFlows.GudduBarrage.Percent.at(-1));
//    //console.log("TotalPercent", SindhFlows.GudduBarrage.TotalPercent.at(-1));

//    //console.log("Storage", SindhFlows.GudduBarrage.Storage.at(-1));
//    //console.log("ActualWD", SindhFlows.GudduBarrage.ActualWD.at(-1));
//    //console.log("ActualWDTotal", ); 
//    LoadCanalFlowChart(SindhFlows.Dates_DD_MM_YY,
//        { title: "U/S", Values: SindhFlows.GudduBarrage.US },
//        { title: "D/S", Values: SindhFlows.GudduBarrage.DS },
//        "Guddu Barrage", "ChartLeft", "line", true, 15);

//}
//function getSlide(title, Actual, Accord, Percent, Remarks) {
//    let HTMLPercent = "";
//    if (!(Percent == NaN || Percent == "NaN" || Percent == undefined || Percent == "")) {
//        let cClass = "stats-small__percentage--still";
//        if (Percent > 0 || Percent == NaN || Percent == "NaN") {
//            cClass = "stats-small__percentage--increase";
//        } else if (Percent < 0) {
//            cClass = "stats-small__percentage--decrease";
//        }
//        else {
//            cClass = "stats-small__percentage--still";
//        }
//        HTMLPercent = ` <div class="stats-small__data">  <span class="stats-small__percentage ${cClass}">${Remarks} ( ${Percent} % )</span>

//                </div>`;
//    }



//    return `
//       <div class="swiper-slide">
//           <div class="stats-small stats-small--1 card card-small">
//               <div class="card-body p-0 d-flex">
//                   <div class="d-flex flex-column m-auto">
//                       <div class="stats-small__data text-center">
//                           <span class="stats-small__label text-uppercase">${title}</span>
//                           <h6 class="stats-small__value count my-3">${Actual}/${Accord}</h6>
//                           <span class="stats-small__label text-uppercase">Acutal/Accord</span>
//                       </div>
//                      ${HTMLPercent}
                      
//                   </div>
//                   <canvas height="154" class="blog-overview-stats-small-Box1Right" width="389" style="display: block; box-sizing: border-box; height: 102.667px; width: 259.333px;"></canvas>
//               </div>
//           </div>
//       </div>
//   `;
//}

'use strict';
(function () {
    const apiUrl = 'https://api.hicsindh.pk/public/FlowBulletins/IndusRiver_Rimstation';
    const prefix = "https://irrigation.sindh.gov.pk/";
    const componentHTML1 = `
        <div class="row content">
            <!-- First HTML structure -->
            <div class="row align-items-center justify-content-center">
                <div class="col-md-4">
                    <div class="input-group">
                        <button class="btn btn-outline-secondary" type="button" id="SFPrevious"><i class='bx bxs-left-arrow'></i></button>
                        <input type="text" id="SFDateRange" class="form-control text-center" aria-label="Select Date"/>
                        <button type="button" class="btn btn-outline-secondary dropdown-toggle dropdown-toggle-split" data-bs-toggle="dropdown" aria-expanded="false"><span class="visually-hidden">Toggle Dropdown</span></button>
                        <ul class="dropdown-menu z-3" id="SFList"></ul>
                        <button class="btn btn-outline-secondary" type="button" id="SFNext"><i class='bx bxs-right-arrow'></i></button>
                        <button class="btn btn-outline-secondary" type="button" id="SFDownload"><i class='bx bxs-cloud-download'></i></button>
                        <button class="btn btn-outline-secondary" type="button" id="SFPrint"><i class='bx bxs-printer'></i></button>
                        <input type="hidden" id="SFID"/>
                    </div>
                </div>
            </div>
            <div class="row align-items-center justify-content-center">
                <img id="SFDisplay" class="img w-100" style="display:none;" />
                <img id="loadingSpinner" class="img w-25" src="/Content/loading.gif" style="display:none;" />
            </div>
        </div>
    `;

    const componentHTML2 = `
       <div class="row content" style="place-content: center;">
            <!-- Second HTML structure -->
            <div class="row">
                <div class="form-row align-items-center">
                    <div class="input-group">
                        <div class="input-group-prepend">
                            <button class="btn btn-outline-secondary" type="button" id="SFPrevious"><i class="fas fa-arrow-left"></i></button>
                        </div>
                        <input type="text" id="SFDateRange" class="form-control text-center" aria-label="Select Date"/>
                        <input type="hidden" id="SFID"/>
                        <div class="input-group-append">
                            <button type="button" class="btn btn-outline-secondary dropdown-toggle dropdown-toggle-split" data-toggle="dropdown" aria-expanded="false"><span class="sr-only">Toggle Dropdown</span></button>
                            <ul class="dropdown-menu z-3" id="SFList"></ul>
                            <button class="btn btn-outline-secondary" type="button" id="SFNext"><i class="fas fa-arrow-right"></i></button>
                            <button class="btn btn-outline-secondary" type="button" id="SFDownload"><i class="fas fa-download"></i></button>
                            <button class="btn btn-outline-secondary" type="button" id="SFPrint"><i class="fas fa-print"></i></button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row align-items-center justify-content-center">
                <img id="SFDisplay" class="img w-100" style="display:none;" />
                <img id="loadingSpinner" class="img w-25" src="/Content/loading.gif" style="display:none;" />
            </div>
        </div>
    `;

    function initializeComponent() {
        let data = {};
        let currentIndex = 0;

        function updatePicture(index) {
            const picture = data.pictures[index];
            $("#SFDateRange").val(moment(picture.getDate).format("DD-MMMM-YY"));
            const imgUrl = prefix + data.url + picture.fileName.replace('.pdf', '.png');

            $("#loadingSpinner").show();
            $("#SFDisplay").hide();

            $("#SFDisplay").attr("src", imgUrl).on('load', function () {
                $("#loadingSpinner").hide();
                $("#SFDisplay").show();
            }).on('error', function () {
                $("#loadingSpinner").hide();
                $(this).attr('src', '/Content/ImageNotAvaiable.jpg').show();
            });

            $("#SFID").val(index);
            $("#SFDownload").attr("href", prefix + data.url + picture.fileName).attr("target", "_blank");
        }

        function populateDropdown() {
            const dropdown = $("#SFList");
            dropdown.empty();
            data.pictures.slice().reverse().forEach((picture, index) => {
                dropdown.append(`<li><a class="dropdown-item" href="#" data-index="${data.pictures.length - 1 - index}">${moment(picture.getDate).format("DD-MMM-YY")}</a></li>`);
            });
        }

        $("#SFPrevious").click(function () {
            if (currentIndex > 0) {
                currentIndex--;
                updatePicture(currentIndex);
            }
        });

        $("#SFNext").click(function () {
            if (currentIndex < data.pictures.length - 1) {
                currentIndex++;
                updatePicture(currentIndex);
            }
        });

        $("#SFList").on("click", ".dropdown-item", function (e) {
            e.preventDefault();
            const index = $(this).data("index");
            currentIndex = index;
            updatePicture(currentIndex);
            $('#SFDateRange').val(moment(data.pictures[currentIndex].getDate).format('DD-MMMM-YY'));
            $('#SFDateRange').data('daterangepicker').setStartDate(moment(data.pictures[currentIndex].getDate));
            $('#SFDateRange').data('daterangepicker').setEndDate(moment(data.pictures[currentIndex].getDate));
        });

        $("#SFDownload").click(function () {
            const picture = data.pictures[currentIndex];
            const pdfUrl = prefix + data.url + picture.fileName;
            window.open(pdfUrl, '_blank');
        });

        $("#SFPrint").click(function () {
            const imgSrc = $("#SFDisplay").attr("src");
            const printWindow = window.open('', '_blank');
            printWindow.document.write(`
                <html>
                <head>
                    <title>Print Image</title>
                    <style>
                        body { text-align: center; margin: 0; padding: 0; }
                        img { max-width: 100%; max-height: 100%; }
                    </style>
                </head>
                <body>
                    <img src="${imgSrc}" id="printImage">
                    <script>
                        const img = document.getElementById('printImage');
                        img.onload = function() {
                            window.print();
                            window.close();
                        };
                    </script>
                </body>
                </html>
            `);
            printWindow.document.close();
        });

        function initializeDatePicker() {
            $('#SFDateRange').daterangepicker({
                autoApply: true,
                alwaysShowCalendars: true,
                singleDatePicker: true,
                showDropdowns: true,
                locale: { format: 'DD-MMMM-YY' },
                drops: "auto",
                startDate: moment(data.pictures[currentIndex].getDate),
                minDate: moment(data.minDate),
                maxDate: moment(data.maxDate),
            }).on('apply.daterangepicker', function (ev, picker) {
                const selectedDate = picker.startDate.format('YYYY-MM-DD');
                const index = data.pictures.findIndex(picture => moment(picture.getDate).format('YYYY-MM-DD') === selectedDate);
                $('#SFDateRange').attr("title", "").tooltip("hide").removeAttr("title").removeClass("border border-primary border-danger");
                if (index !== -1) {
                    currentIndex = index;
                    updatePicture(currentIndex);
                }
                else {
                    $('#SFDateRange').attr("title", "Sorry Data is Not Available").tooltip("show").addClass("border border-danger");
                }
            });
        }

        $.ajax({
            url: apiUrl,
            method: 'GET',
            success: function (response) {
                data = response;
                currentIndex = data.pictures.length - 1;
                populateDropdown();
                updatePicture(currentIndex);
                initializeDatePicker();
            },
            error: function () {
                alert('Failed to fetch data from the API.');
            }
        });

        const style = document.createElement('style');
        style.innerHTML = `#SFList { max-height: 150px; overflow-y: auto; }`;
        document.head.appendChild(style);
    }

    // Append the component to a container and initialize it
    window.loadRimstation = function (containerId, htmlOption) {
        const container = $("#" + containerId);
        container.html(htmlOption === 1 ? componentHTML1 : componentHTML2);
        $(document).ready(initializeComponent);
    }
})();

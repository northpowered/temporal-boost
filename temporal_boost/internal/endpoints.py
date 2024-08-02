from robyn import Response


async def custom_css():
    content = """
            /*
                DEMO STYLE
            */

            @import "https://fonts.googleapis.com/css?family=Poppins:300,400,500,600,700";
            body {
                font-family: Aeonik,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,
                Helvetica Neue,Arial,Noto Sans,sans-serif,
                "Apple Color Emoji","Segoe UI Emoji",Segoe UI Symbol,"Noto Color Emoji";
                background: #fafafa;
            }

            p {
                font-family: 'Poppins', sans-serif;
                font-size: 1.1em;
                font-weight: 300;
                line-height: 1.7em;
                color: #999;
            }

            a,
            a:hover,
            a:focus {
                color: inherit;
                text-decoration: none;
                transition: all 0.3s;
            }

            .navbar {
                padding: 15px 10px;
                background: #fff;
                border: none;
                border-radius: 0;
                margin-bottom: 40px;
                box-shadow: 1px 1px 3px rgba(0, 0, 0, 0.1);
            }

            .navbar-btn {
                box-shadow: none;
                outline: none !important;
                border: none;
            }

            .line {
                width: 100%;
                height: 1px;
                border-bottom: 1px dashed #ddd;
                margin: 40px 0;
            }

            /* ---------------------------------------------------
                SIDEBAR STYLE
            ----------------------------------------------------- */

            .wrapper {
                display: flex;
                width: 100%;
                align-items: stretch;
            }

            #sidebar {
                min-width: 250px;
                max-width: 250px;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #fff;
                transition: all 0.3s;
            }

            #sidebar.active {
                margin-left: -250px;
            }

            #sidebar .sidebar-header {
                padding: 20px;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #CDF5FD
            }

            .accordion-dark {
                border: 1px solid #A7E6FF;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #CDF5FD

            }

            .accordion-dark[aria-expanded="true"] {
                border: 1px solid #A7E6FF;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #CDF5FD

            }

            .table-temporal-style {
                color: #CDF5FD
            }

            #sidebar ul.components {
                padding: 20px 0;
                border-bottom: 1px solid #A7E6FF;
            }

            #sidebar ul p {
                color: #3ABEF9;
                padding: 10px;
            }

            #sidebar ul li a {
                padding: 10px;
                font-size: 1.1em;
                display: block;
            }

            #sidebar ul li a:hover {
                color: #A7E6FF;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
            }

            #sidebar ul li.active>a,
            a[aria-expanded="true"] {
                color: #3ABEF9;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
            }

            a[data-toggle="collapse"] {
                position: relative;
            }

            .dropdown-toggle::after {
                display: block;
                position: absolute;
                top: 50%;
                right: 20px;
                transform: translateY(-50%);
            }

            ul ul a {
                font-size: 0.9em !important;
                padding-left: 30px !important;
                bbackground: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #fff;
            }

            ul.CTAs {
                padding: 20px;
            }

            ul.CTAs a {
                text-align: center;
                font-size: 0.9em !important;
                display: block;
                border-radius: 5px;
                margin-bottom: 5px;
            }

            a.download {
                background: #fff;
                color: #00A9FF;
            }

            a.article,
            a.article:hover {
                background-image: linear-gradient(45deg,#b664ff,#444ce7);
                color: rgb(248 250 252 / var(--tw-text-opacity));
            }

            /* ---------------------------------------------------
                CONTENT STYLE
            ----------------------------------------------------- */

            #content {
                width: 100%;
                padding: 20px;
                min-height: 100vh;
                transition: all 0.3s;
                background: rgb(31 32 63 / var(--tw-bg-opacity));
                --tw-bg-opacity: 1;
                color: #fff;
            }

            /* ---------------------------------------------------
                MEDIAQUERIES
            ----------------------------------------------------- */

            @media (max-width: 768px) {
                #sidebar {
                    margin-left: -250px;
                }
                #sidebar.active {
                    margin-left: 0;
                }
                #sidebarCollapse span {
                    display: none;
                }
            }
        """
    return Response(status_code=200, headers={"Content-Type": "text/css; charset=utf-8"}, description=content)


async def custom_js():
    content = """$(document).ready(function () {

            $('#sidebarCollapse').on('click', function () {
                $('#sidebar').toggleClass('active');
            });

            $('.workers-nav-element').on('click', function () {
                $('#flush-workers').toggle(true);
            });
            $('#workers-main-header').on('click', function () {
                $('#flush-workers').toggle();
            });

            $('.workflows-nav-element').on('click', function () {
                $('#flush-workflows').toggle(true);
            });
            $('#workflows-main-header').on('click', function () {
                $('#flush-workflows').toggle();
            });

            $('.activities-nav-element').on('click', function () {
                $('#flush-activities').toggle(true);
            });
            $('#activities-main-header').on('click', function () {
                $('#flush-activities').toggle();
            });

            $('.signals-nav-element').on('click', function () {
                $('#flush-signals').toggle(true);
            });
            $('#signals-main-header').on('click', function () {
                $('#flush-signals').toggle();
            });

            $('.schemas-nav-element').on('click', function () {
                $('#flush-schemas').toggle(true);
            });
            $('#schemas-main-header').on('click', function () {
                $('#flush-schemas').toggle();
            });

        });"""
    return Response(status_code=200, headers={"Content-Type": "text/javascript; charset=utf-8"}, description=content)

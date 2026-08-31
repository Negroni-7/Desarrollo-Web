<html>
    <head>
        <title>Pagina principal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>
    </head>
    <body>
        <!--Navbar (barra superior de navegacion)-->

        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
            <div class="container-fluid">

                <a class="navbar-brand" href="index.php">Logo</a>

                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="collapsibleNavbar">
                    <ul class="navbar-nav">

                        <!-- Item en el navbar con menu desplegable -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Empresa</a>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="empresa.php">Quienes Somos</a></li>
                                <li><a class="dropdown-item" href="#">Nuestro Equipo</a></li>
                                <li><a class="dropdown-item" href="#">Mision</a></li>
                            </ul>
                        </li>

                        <!-- Item simple en navbar -->
                        <li class="nav-item">
                            <a class="nav-link" href="productos.php">Productos</a>
                        </li>

                        <!-- Item simple en navbar -->
                        <li class="nav-item">
                            <a class="nav-link" href="contacto.php">Contacto</a>
                        </li>
                        <!-- Item simple en navbar -->

                        <li class="nav-item">
                            <a class="nav-link" href="ayuda.php">Ayuda</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        <!-- Container -->
         <div class="container-fluid bg-dark">
            <div class="col-4"></div>
            <div class="col-4" style="color:white"><strong>Ejemplo de que es Empresa Fantasma SPA</strong></div>
            <div class="col-4"></div>
        </div>
        <div class="containter-fluid bg-warning">
            <a href="index.php">Volver</a>
        </div>

        <!-- Footer (la parte inferior de la pagina)-->
        <div class="container-fluid bg-dark">
            <div class="row">
                <div class="col-4"></div>
                <div class="col-4" style="color:white"><strong>MiEmpresaFantasma@2070</strong></div>
                <div class="col-4"></div>
            </div>
        </div>
        <!-- Modal -->
    </body>
</html>